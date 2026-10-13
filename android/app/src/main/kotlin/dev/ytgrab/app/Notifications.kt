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

    fun progress(context: Context, status: DownloadStatus.Running): Notification {
        val cancel = PendingIntent.getService(
            context, 1,
            Intent(context, DownloadService::class.java).setAction(DownloadService.ACTION_CANCEL),
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT,
        )
        val known = status.percent >= 0
        return NotificationCompat.Builder(context, CHANNEL)
            .setSmallIcon(R.drawable.ic_notification)
            .setContentTitle(status.title)
            .setContentText(listOf(status.state, status.stats).filter { it.isNotEmpty() }.joinToString("  ·  "))
            .setProgress(100, if (known) status.percent.toInt() else 0, !known)
            .setOngoing(true)
            .setOnlyAlertOnce(true)
            .setCategory(NotificationCompat.CATEGORY_PROGRESS)
            .setContentIntent(openApp(context))
            .addAction(0, context.getString(R.string.cancel), cancel)
            .build()
    }

    /** A lasting note once the download ends, for when the app isn't on screen. */
    @SuppressLint("MissingPermission") // checked by areNotificationsEnabled()
    fun result(context: Context, status: DownloadStatus) {
        val manager = NotificationManagerCompat.from(context)
        if (!manager.areNotificationsEnabled()) return
        val builder = NotificationCompat.Builder(context, CHANNEL)
            .setSmallIcon(R.drawable.ic_notification)
            .setAutoCancel(true)
            .setContentIntent(openApp(context))
        when (status) {
            is DownloadStatus.Done -> {
                val view = Intent(Intent.ACTION_VIEW)
                    .setDataAndType(status.file.uri, status.file.mime)
                    .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_ACTIVITY_NEW_TASK)
                builder.setContentTitle(context.getString(R.string.notif_saved))
                    .setContentText(status.title)
                    .setContentIntent(
                        PendingIntent.getActivity(
                            context, 2, view,
                            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT,
                        )
                    )
            }
            is DownloadStatus.Failed -> builder.setContentTitle(context.getString(R.string.download_failed))
                .setContentText(status.message)
                .setStyle(NotificationCompat.BigTextStyle().bigText(status.message))
            else -> return
        }
        manager.notify(RESULT_ID, builder.build())
    }

    @SuppressLint("MissingPermission")
    fun update(context: Context, status: DownloadStatus.Running) {
        val manager = NotificationManagerCompat.from(context)
        if (manager.areNotificationsEnabled()) manager.notify(PROGRESS_ID, progress(context, status))
    }
}
