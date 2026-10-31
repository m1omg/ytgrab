package dev.ytgrab.app

import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.os.Build
import android.os.IBinder
import android.os.PowerManager
import android.os.SystemClock
import androidx.core.content.ContextCompat
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.io.File

/**
 * Works through the download queue as a foreground service, one item at a
 * time, so downloads carry on while the user goes back to YouTube or turns
 * the screen off.
 */
class DownloadService : Service() {
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Main.immediate)
    private var job: Job? = null
    private var wakeLock: PowerManager.WakeLock? = null
    private var lastNotified = 0L

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        when (intent?.action) {
            ACTION_START -> start()
            ACTION_CANCEL -> Downloads.cancelRunning()
            ACTION_CANCEL_ALL -> Downloads.cancelAll()
        }
        if (job?.isActive != true) stopSelf()
        return START_NOT_STICKY
    }

    private fun start() {
        // Every startForegroundService() wants a startForeground(), even while
        // the queue is already being worked through.
        val running = Downloads.queue.value.firstOrNull { it.state == ItemState.RUNNING }
        val notification = Notifications.progress(this, running, waiting())
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            startForeground(Notifications.PROGRESS_ID, notification, ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC)
        } else {
            startForeground(Notifications.PROGRESS_ID, notification)
        }
        if (job?.isActive == true) return

        Downloads.stopAll.set(false)
        // Keep the CPU awake with the screen off; released when the queue is done.
        val lock = (getSystemService(POWER_SERVICE) as PowerManager)
            .newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "ytgrab:download")
            .apply { setReferenceCounted(false) }
        wakeLock = lock
        job = scope.launch {
            val finished = mutableListOf<QueueItem>()
            while (true) {
                val item = Downloads.takeNext() ?: break
                lock.acquire(4 * 60 * 60 * 1000L)  // each download gets the full allowance
                try {
                    run(item)
                } catch (e: CancellationException) {
                    // The service is going away; onDestroy() has seen to the queue,
                    // and what waits carries on when DLPizer is next opened.
                    throw e
                } catch (e: Exception) {
                    Downloads.update(item.id) {
                        it.copy(state = ItemState.FAILED, error = e.localizedMessage ?: e.toString())
                    }
                }
                Downloads.queue.value.firstOrNull { it.id == item.id }?.takeIf { it.finished }?.let(finished::add)
            }
            Notifications.result(this@DownloadService, finished)
            lock.takeIf { it.isHeld }?.release()
            stopForeground(STOP_FOREGROUND_REMOVE)
            stopSelf()
        }
    }

    private suspend fun run(item: QueueItem) {
        publish(item.id, force = true) { it.copy(progress = getString(R.string.starting)) }
        val work = File(cacheDir, "downloads").apply { mkdirs() }
        val listener = DownloadListener(
            itemId = item.id,
            progress = { json ->
                publish(item.id) {
                    it.copy(
                        title = it.title.ifEmpty { json.optString("title") },
                        progress = json.getString("state"),
                        stats = json.getString("stats"),
                        percent = json.getDouble("percent").toFloat(),
                    )
                }
            },
            stage = { text -> publish(item.id) { it.copy(progress = text, stats = "", percent = -1f) } },
        )
        val result = Engine.download(this, item.request, work, listener)
        when {
            result.optBoolean("ok") -> {
                publish(item.id, force = true) {
                    it.copy(progress = getString(R.string.saving), stats = "", percent = -1f)
                }
                val file = File(result.getString("path"))
                val saved = withContext(Dispatchers.IO) {
                    try {
                        Saver.save(this@DownloadService, file)
                    } finally {
                        file.delete()
                    }
                }
                Downloads.update(item.id) {
                    it.copy(state = ItemState.DONE, file = saved, title = it.title.ifEmpty { file.nameWithoutExtension })
                }
            }
            result.has("playlist") -> {
                val entries = result.getJSONObject("playlist").getJSONArray("entries")
                Downloads.expand(
                    item.id,
                    List(entries.length()) {
                        val entry = entries.getJSONObject(it)
                        entry.getString("url") to entry.optString("title")
                    },
                    getString(R.string.playlist_empty),
                )
            }
            result.optBoolean("cancelled") -> Downloads.update(item.id) { it.copy(state = ItemState.CANCELLED) }
            else -> Downloads.update(item.id) { it.copy(state = ItemState.FAILED, error = result.optString("error")) }
        }
    }

    private fun waiting() = Downloads.queue.value.count { it.state == ItemState.WAITING }

    /** Update a running item, and its notification at most once a second. */
    private fun publish(id: Long, force: Boolean = false, change: (QueueItem) -> QueueItem) {
        Downloads.update(id) { if (it.cancelling) it else change(it) }  // "Cancelling…" stays up
        // Android drops notification updates that come too often.
        val now = SystemClock.elapsedRealtime()
        if (force || now - lastNotified >= 1000) {
            lastNotified = now
            Downloads.queue.value.firstOrNull { it.id == id }?.let { Notifications.update(this, it, waiting()) }
        }
    }

    /**
     * Android 15 and later give a data-sync service six hours a day, then ask
     * it to stop; one that doesn't is killed with the whole app.
     */
    override fun onTimeout(startId: Int, fgsType: Int) {
        stopSelf()
    }

    override fun onDestroy() {
        Downloads.stopAll.set(true)
        // A download the system cut short can be tried again from the list.
        Downloads.queue.update { list ->
            list.map { if (it.state == ItemState.RUNNING) it.copy(state = ItemState.CANCELLED) else it }
        }
        wakeLock?.takeIf { it.isHeld }?.release()
        scope.cancel()
        super.onDestroy()
    }

    companion object {
        const val ACTION_START = "dev.ytgrab.app.START"
        const val ACTION_CANCEL = "dev.ytgrab.app.CANCEL"
        const val ACTION_CANCEL_ALL = "dev.ytgrab.app.CANCEL_ALL"

        /** Start working through the queue, or carry on if it already is. */
        fun start(context: Context) {
            ContextCompat.startForegroundService(
                context, Intent(context, DownloadService::class.java).setAction(ACTION_START),
            )
        }
    }
}
