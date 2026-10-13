package dev.ytgrab.app

import android.app.Application
import android.graphics.BitmapFactory
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.ui.graphics.ImageBitmap
import androidx.compose.ui.graphics.asImageBitmap
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL

enum class Mode(val key: String) { VIDEO("video"), AUDIO("audio"), MP3("mp3"), TRANSCRIPT("transcript") }

data class Transcript(val code: String, val auto: Boolean)

data class VideoInfo(
    val title: String,
    val uploader: String,
    val duration: Int,
    val thumbnail: String,
    val heights: List<Int>,
    val isLive: Boolean,
    val transcripts: List<Transcript>,
) {
    companion object {
        fun from(json: JSONObject): VideoInfo {
            val heights = json.getJSONArray("heights")
            val tracks = json.getJSONArray("transcripts")
            return VideoInfo(
                title = json.optString("title"),
                uploader = json.optString("uploader"),
                duration = json.optInt("duration"),
                thumbnail = json.optString("thumbnail"),
                heights = List(heights.length()) { heights.getInt(it) },
                isLive = json.optBoolean("is_live"),
                transcripts = List(tracks.length()) {
                    val t = tracks.getJSONObject(it)
                    Transcript(t.getString("code"), t.optBoolean("auto"))
                },
            )
        }
    }
}

class MainViewModel(app: Application) : AndroidViewModel(app) {
    var url by mutableStateOf("")
    var fetching by mutableStateOf(false)
        private set
    var info by mutableStateOf<VideoInfo?>(null)
        private set
    var thumbnail by mutableStateOf<ImageBitmap?>(null)
        private set
    var message by mutableStateOf<String?>(null)

    var mode by mutableStateOf(Mode.VIDEO)
    var height by mutableStateOf("best")
    var container by mutableStateOf("mp4")
    var audioStream by mutableStateOf("best")
    var bitrate by mutableStateOf("192")
    var transcriptLang by mutableStateOf<String?>(null)
    var transcriptFormat by mutableStateOf("txt")
    var embed by mutableStateOf(true)

    private var fetchJob: Job? = null

    init {
        // Python takes a moment to start the first time; do it before it's needed.
        viewModelScope.launch { runCatching { Engine.warmUp(getApplication()) } }
    }

    /** A shared "Watch this: https://youtu.be/..." becomes just the link. */
    fun onShared(text: String) {
        url = LINK.find(text)?.value ?: text.trim()
        fetch()
    }

    fun fetch() {
        val link = url.trim()
        if (link.isEmpty() || fetchJob?.isActive == true) return
        fetching = true
        message = null
        fetchJob = viewModelScope.launch {
            try {
                val result = Engine.fetchInfo(getApplication(), link)
                if (result.optBoolean("ok")) {
                    show(VideoInfo.from(result.getJSONObject("info")))
                } else {
                    message = result.optString("error")
                }
            } catch (e: Exception) {
                message = e.localizedMessage ?: e.toString()
            } finally {
                fetching = false
            }
        }
    }

    private fun show(video: VideoInfo) {
        info = video
        thumbnail = null
        if (height != "best" && height.toIntOrNull() !in video.heights) height = "best"
        transcriptLang = defaultTranscript(video.transcripts)
        if (video.thumbnail.isNotEmpty()) {
            viewModelScope.launch { thumbnail = loadImage(video.thumbnail) }
        }
    }

    /** The interface language first, then English, then whatever is listed first. */
    private fun defaultTranscript(tracks: List<Transcript>): String? {
        val wanted = listOf(Engine.language(getApplication()), "en")
        for (lang in wanted) {
            tracks.firstOrNull { it.code == lang || it.code.substringBefore('-') == lang }?.let { return it.code }
        }
        return tracks.firstOrNull()?.code
    }

    /** What the Download button should fetch, or null if something is missing. */
    fun request(): DownloadRequest? {
        val link = url.trim().takeIf { it.isNotEmpty() } ?: return null
        val title = info?.title?.takeIf { it.isNotEmpty() } ?: link
        return when (mode) {
            Mode.VIDEO -> DownloadRequest(link, title, "video", height, container, embed)
            Mode.AUDIO -> DownloadRequest(link, title, "audio", audioStream, "mp4", embed)
            Mode.MP3 -> DownloadRequest(link, title, "mp3", bitrate, "mp4", embed)
            Mode.TRANSCRIPT -> transcriptLang?.let {
                DownloadRequest(link, title, "transcript", it, transcriptFormat, false)
            }
        }
    }

    private suspend fun loadImage(address: String): ImageBitmap? = withContext(Dispatchers.IO) {
        runCatching {
            val connection = URL(address).openConnection() as HttpURLConnection
            connection.connectTimeout = 15_000
            connection.readTimeout = 15_000
            connection.inputStream.use { BitmapFactory.decodeStream(it)?.asImageBitmap() }
        }.getOrNull()
    }

    companion object {
        private val LINK = Regex("""https?://\S+""")
    }
}
