package dev.ytgrab.app

import android.app.Service
import android.content.Intent
import android.content.pm.ServiceInfo
import android.os.Build
import android.os.IBinder
import android.os.PowerManager
import android.os.SystemClock
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.io.File

/**
 * Runs one download as a foreground service, so it carries on while the user
 * goes back to YouTube or turns the screen off.
 */
class DownloadService : Service() {
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Main.immediate)
    private var job: Job? = null
    private var wakeLock: PowerManager.WakeLock? = null
    private var lastNotified = 0L

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        when (intent?.action) {
            ACTION_START -> DownloadRequest.from(intent)?.let(::start)
            ACTION_CANCEL -> requestCancel(this)
        }
        if (job?.isActive != true) stopSelf()
        return START_NOT_STICKY
    }

    private fun start(request: DownloadRequest) {
        if (job?.isActive == true) return
        Downloads.cancelRequested.set(false)
        val first = DownloadStatus.Running(request.title, getString(R.string.starting))
        Downloads.status.value = first
        val notification = Notifications.progress(this, first)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            startForeground(Notifications.PROGRESS_ID, notification, ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC)
        } else {
            startForeground(Notifications.PROGRESS_ID, notification)
        }
        // Keep the CPU awake with the screen off; released when the download ends.
        wakeLock = (getSystemService(POWER_SERVICE) as PowerManager)
            .newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "ytgrab:download")
            .apply { acquire(4 * 60 * 60 * 1000L) }

        job = scope.launch {
            val result = try {
                run(request)
            } catch (e: Exception) {
                DownloadStatus.Failed(request.title, e.localizedMessage ?: e.toString())
            }
            Downloads.status.value = result
            Notifications.result(this@DownloadService, result)
            wakeLock?.takeIf { it.isHeld }?.release()
            stopForeground(STOP_FOREGROUND_REMOVE)
            stopSelf()
        }
    }

    private suspend fun run(request: DownloadRequest): DownloadStatus {
        val work = File(cacheDir, "downloads").apply { mkdirs() }
        val listener = DownloadListener(
            progress = { json ->
                publish(
                    DownloadStatus.Running(
                        request.title, json.getString("state"), json.getString("stats"),
                        json.getDouble("percent").toFloat(),
                    )
                )
            },
            stage = { text -> publish(DownloadStatus.Running(request.title, text)) },
        )
        val result = Engine.download(this, request, work, listener)
        return when {
            result.optBoolean("ok") -> {
                publish(DownloadStatus.Running(request.title, getString(R.string.saving)), force = true)
                val file = File(result.getString("path"))
                val saved = withContext(Dispatchers.IO) {
                    try {
                        Saver.save(this@DownloadService, file)
                    } finally {
                        file.delete()
                    }
                }
                DownloadStatus.Done(request.title, saved)
            }
            result.optBoolean("cancelled") -> DownloadStatus.Cancelled(request.title)
            else -> DownloadStatus.Failed(request.title, result.optString("error"))
        }
    }

    private fun publish(status: DownloadStatus.Running, force: Boolean = false) {
        if (Downloads.cancelRequested.get()) return  // "Cancelling…" stays up
        Downloads.status.value = status
        // Android drops notification updates that come too often.
        val now = SystemClock.elapsedRealtime()
        if (force || now - lastNotified >= 1000) {
            lastNotified = now
            Notifications.update(this, status)
        }
    }

    override fun onDestroy() {
        Downloads.cancelRequested.set(true)
        wakeLock?.takeIf { it.isHeld }?.release()
        scope.cancel()
        super.onDestroy()
    }

    companion object {
        const val ACTION_START = "dev.ytgrab.app.START"
        const val ACTION_CANCEL = "dev.ytgrab.app.CANCEL"

        fun requestCancel(context: android.content.Context) {
            val current = Downloads.status.value as? DownloadStatus.Running ?: return
            Downloads.cancelRequested.set(true)
            val cancelling = current.copy(state = context.getString(R.string.cancelling), stats = "", percent = -1f)
            Downloads.status.value = cancelling
            Notifications.update(context, cancelling)
        }
    }
}
