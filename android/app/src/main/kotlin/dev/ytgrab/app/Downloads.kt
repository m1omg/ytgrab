package dev.ytgrab.app

import android.net.Uri
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.update
import org.json.JSONObject
import java.util.concurrent.atomic.AtomicBoolean
import java.util.concurrent.atomic.AtomicLong

/** What to download, in the terms ytgrab/core.py's download() takes. */
data class DownloadRequest(
    val url: String,
    val title: String,
    val mode: String,
    val quality: String,
    val container: String,
    val embed: Boolean,
    val part: Part? = null,
)

/** A finished file, already in the public Downloads folder. */
data class SavedFile(val uri: Uri, val mime: String, val location: String)

enum class ItemState { WAITING, RUNNING, DONE, FAILED, CANCELLED }

private val nextId = AtomicLong(1)

/** One download in the queue, and how far it has got. */
data class QueueItem(
    val request: DownloadRequest,
    val id: Long = nextId.getAndIncrement(),
    val state: ItemState = ItemState.WAITING,
    /** Known up front for a video that was fetched; otherwise learnt as it downloads. */
    val title: String = request.title,
    /** While it runs: what it's doing, its numbers, and the percent (negative while unknown). */
    val progress: String = "",
    val stats: String = "",
    val percent: Float = -1f,
    val cancelling: Boolean = false,
    val file: SavedFile? = null,
    val error: String? = null,
) {
    val finished: Boolean
        get() = state == ItemState.DONE || state == ItemState.FAILED || state == ItemState.CANCELLED

    val label: String
        get() = title.ifEmpty { request.url }
}

/**
 * The download queue, shared by the service that works through it and the
 * screen that shows it. Items run one at a time, in order: YouTube is
 * quicker to ask whether you're a bot when several run at once.
 */
object Downloads {
    val queue = MutableStateFlow<List<QueueItem>>(emptyList())

    /** Stops whatever runs when the service itself goes away. */
    val stopAll = AtomicBoolean(false)

    val busy: Boolean
        get() = queue.value.any { it.state == ItemState.WAITING || it.state == ItemState.RUNNING }

    fun add(requests: List<DownloadRequest>) = queue.update { list -> list + requests.map { QueueItem(it) } }

    fun update(id: Long, change: (QueueItem) -> QueueItem) =
        queue.update { list -> list.map { if (it.id == id) change(it) else it } }

    /** The next item to run, marked as running; null when nothing is waiting. */
    fun takeNext(): QueueItem? {
        var taken: QueueItem? = null
        queue.update { list ->
            val index = list.indexOfFirst { it.state == ItemState.WAITING }
            taken = if (index < 0) null else list[index].copy(state = ItemState.RUNNING)
            if (index < 0) list else list.toMutableList().also { it[index] = taken!! }
        }
        return taken
    }

    fun isCancelled(id: Long): Boolean =
        stopAll.get() || queue.value.firstOrNull { it.id == id }?.cancelling == true

    /** Stop a download, or keep a waiting one from starting. */
    fun cancel(id: Long) = update(id) {
        when (it.state) {
            ItemState.RUNNING -> it.copy(cancelling = true)
            ItemState.WAITING -> it.copy(state = ItemState.CANCELLED)
            else -> it
        }
    }

    fun cancelRunning() = queue.update { list ->
        list.map { if (it.state == ItemState.RUNNING) it.copy(cancelling = true) else it }
    }

    /** Stop what runs and drop everything still waiting. */
    fun cancelAll() = queue.update { list ->
        list.filter { it.state != ItemState.WAITING }
            .map { if (it.state == ItemState.RUNNING) it.copy(cancelling = true) else it }
    }

    fun retry(id: Long) = update(id) {
        if (it.state == ItemState.FAILED || it.state == ItemState.CANCELLED) QueueItem(it.request, it.id, title = it.title) else it
    }

    fun remove(id: Long) = queue.update { list -> list.filterNot { it.id == id && it.state != ItemState.RUNNING } }

    fun clearFinished() = queue.update { list -> list.filterNot { it.finished } }

    /** Put a playlist's videos where its link stood, with the link's settings. */
    fun expand(id: Long, entries: List<Pair<String, String>>, emptyError: String) = queue.update { list ->
        val index = list.indexOfFirst { it.id == id }
        if (index < 0) return@update list
        val item = list[index]
        // A playlist listing itself would never end.
        val videos = entries.filter { (url, _) -> url != item.request.url }
        if (videos.isEmpty()) {
            list.toMutableList().also { it[index] = item.copy(state = ItemState.FAILED, error = emptyError) }
        } else {
            list.subList(0, index) +
                videos.map { (url, title) -> QueueItem(item.request.copy(url = url, title = title)) } +
                list.subList(index + 1, list.size)
        }
    }
}

/**
 * Handed to the Python bridge, which calls these three methods by name while
 * a download runs. They are called on the download thread.
 */
class DownloadListener(
    private val itemId: Long,
    private val progress: (JSONObject) -> Unit,
    private val stage: (String) -> Unit,
) {
    fun onProgress(json: String) = progress(JSONObject(json))

    fun onStage(text: String) = stage(text)

    fun isCancelled(): Boolean = Downloads.isCancelled(itemId)
}
