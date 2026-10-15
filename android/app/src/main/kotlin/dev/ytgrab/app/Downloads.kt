package dev.ytgrab.app

import android.content.Intent
import android.net.Uri
import kotlinx.coroutines.flow.MutableStateFlow
import org.json.JSONObject
import java.util.concurrent.atomic.AtomicBoolean

/** What to download, in the terms ytgrab/core.py's download() takes. */
data class DownloadRequest(
    val url: String,
    val title: String,
    val mode: String,
    val quality: String,
    val container: String,
    val embed: Boolean,
    val part: Part? = null,
) {
    fun putInto(intent: Intent): Intent = intent
        .putExtra(EXTRA_URL, url)
        .putExtra(EXTRA_TITLE, title)
        .putExtra(EXTRA_MODE, mode)
        .putExtra(EXTRA_QUALITY, quality)
        .putExtra(EXTRA_CONTAINER, container)
        .putExtra(EXTRA_EMBED, embed)
        .putExtra(EXTRA_PART_START, part?.start ?: -1)
        .putExtra(EXTRA_PART_END, part?.end ?: -1)

    companion object {
        private const val EXTRA_URL = "url"
        private const val EXTRA_TITLE = "title"
        private const val EXTRA_MODE = "mode"
        private const val EXTRA_QUALITY = "quality"
        private const val EXTRA_CONTAINER = "container"
        private const val EXTRA_EMBED = "embed"
        private const val EXTRA_PART_START = "part_start"
        private const val EXTRA_PART_END = "part_end"

        fun from(intent: Intent): DownloadRequest? = DownloadRequest(
            url = intent.getStringExtra(EXTRA_URL) ?: return null,
            title = intent.getStringExtra(EXTRA_TITLE).orEmpty(),
            mode = intent.getStringExtra(EXTRA_MODE) ?: return null,
            quality = intent.getStringExtra(EXTRA_QUALITY) ?: return null,
            container = intent.getStringExtra(EXTRA_CONTAINER) ?: return null,
            embed = intent.getBooleanExtra(EXTRA_EMBED, true),
            part = intent.getIntExtra(EXTRA_PART_START, -1).takeIf { it >= 0 }?.let { start ->
                Part(start, intent.getIntExtra(EXTRA_PART_END, -1).takeIf { it >= 0 })
            },
        )
    }
}

/** A finished file, already in the public Downloads folder. */
data class SavedFile(val uri: Uri, val mime: String, val location: String)

sealed interface DownloadStatus {
    data object Idle : DownloadStatus

    /** percent is negative while the size is still unknown. */
    data class Running(
        val title: String,
        val state: String,
        val stats: String = "",
        val percent: Float = -1f,
    ) : DownloadStatus

    data class Done(val title: String, val file: SavedFile) : DownloadStatus
    data class Failed(val title: String, val message: String) : DownloadStatus
    data class Cancelled(val title: String) : DownloadStatus
}

/** The one download that can run at a time, shared by the service and the screen. */
object Downloads {
    val status = MutableStateFlow<DownloadStatus>(DownloadStatus.Idle)
    val cancelRequested = AtomicBoolean(false)

    val isRunning: Boolean get() = status.value is DownloadStatus.Running
}

/**
 * Handed to the Python bridge, which calls these three methods by name while
 * a download runs. They are called on the download thread.
 */
class DownloadListener(
    private val progress: (JSONObject) -> Unit,
    private val stage: (String) -> Unit,
) {
    fun onProgress(json: String) = progress(JSONObject(json))

    fun onStage(text: String) = stage(text)

    fun isCancelled(): Boolean = Downloads.cancelRequested.get()
}
