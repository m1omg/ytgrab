package dev.ytgrab.app

import android.annotation.SuppressLint
import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.os.Build
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat

object Notifications {
    private const val CHANNEL = "downloads"
    const val PROGRESS_ID = 1
    private const val RESULT_ID = 2

    fun createChannel(context: Context) {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                CHANNEL, context.getString(R.string.channel_downloads),
                NotificationManager.IMPORTANCE_LOW,
            )
            context.getSystemService(NotificationManager::class.java).createNotificationChannel(channel)
        }
    }

    private fun openApp(context: Context): PendingIntent = PendingIntent.getActivity(
        context, 0,
        Intent(context, MainActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP),
        PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT,
    )

    private fun serviceAction(context: Context, code: Int, action: String): PendingIntent = PendingIntent.getService(
        context, code,
        Intent(context, DownloadService::class.java).setAction(action),
        PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT,
    )

    /** The download that is running (null just before the first starts), and how many wait. */
    fun progress(context: Context, item: QueueItem?, waiting: Int): Notification {
        val state = when {
            item == null -> context.getString(R.string.starting)
            item.cancelling -> context.getString(R.string.cancelling)
            else -> item.progress.ifEmpty { context.getString(R.string.starting) }
        }
        val known = item != null && item.percent >= 0 && !item.cancelling
        val builder = NotificationCompat.Builder(context, CHANNEL)
            .setSmallIcon(R.drawable.ic_notification)
            .setContentTitle(item?.label ?: context.getString(R.string.app_name))
            .setContentText(listOf(state, item?.stats.orEmpty()).filter { it.isNotEmpty() }.joinToString("  ·  "))
            .setProgress(100, if (known) item?.percent?.toInt() ?: 0 else 0, !known)
            .setOngoing(true)
            .setOnlyAlertOnce(true)
            .setCategory(NotificationCompat.CATEGORY_PROGRESS)
            .setContentIntent(openApp(context))
            .addAction(0, context.getString(R.string.cancel), serviceAction(context, 1, DownloadService.ACTION_CANCEL))
        if (waiting > 0) {
            builder.setSubText(context.getString(R.string.notif_waiting, waiting))
                .addAction(0, context.getString(R.string.queue_cancel_all),
                    serviceAction(context, 3, DownloadService.ACTION_CANCEL_ALL))
        }
        return builder.build()
    }

    @SuppressLint("MissingPermission")
    fun update(context: Context, item: QueueItem, waiting: Int) {
        val manager = NotificationManagerCompat.from(context)
        if (manager.areNotificationsEnabled()) manager.notify(PROGRESS_ID, progress(context, item, waiting))
    }

    /**
     * A lasting note once the queue runs dry, for when the app isn't on
     * screen: the file itself after a single download, a count after several.
     */
    @SuppressLint("MissingPermission") // checked by areNotificationsEnabled()
    fun result(context: Context, finished: List<QueueItem>) {
        val manager = NotificationManagerCompat.from(context)
        if (!manager.areNotificationsEnabled() || finished.isEmpty()) return
        val builder = NotificationCompat.Builder(context, CHANNEL)
            .setSmallIcon(R.drawable.ic_notification)
            .setAutoCancel(true)
            .setContentIntent(openApp(context))
        val single = finished.singleOrNull()
        when {
            single == null -> {
                val counts = listOf(
                    R.string.notif_count_saved to ItemState.DONE,
                    R.string.notif_count_failed to ItemState.FAILED,
                    R.string.notif_count_cancelled to ItemState.CANCELLED,
                ).mapNotNull { (text, state) ->
                    finished.count { it.state == state }.takeIf { it > 0 }?.let { context.getString(text, it) }
                }
                builder.setContentTitle(context.getString(R.string.notif_queue_done))
                    .setContentText(counts.joinToString("  ·  "))
            }
            single.state == ItemState.DONE && single.file != null -> {
                val view = Intent(Intent.ACTION_VIEW)
                    .setDataAndType(single.file.uri, single.file.mime)
                    .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_ACTIVITY_NEW_TASK)
                builder.setContentTitle(context.getString(R.string.notif_saved))
                    .setContentText(single.label)
                    .setContentIntent(
                        PendingIntent.getActivity(
                            context, 2, view,
                            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT,
                        )
                    )
            }
            single.state == ItemState.FAILED -> {
                val message = single.error.orEmpty()
                builder.setContentTitle(context.getString(R.string.download_failed))
                    .setContentText(message)
                    .setStyle(NotificationCompat.BigTextStyle().bigText(message))
            }
            else -> return
        }
        manager.notify(RESULT_ID, builder.build())
    }
}
