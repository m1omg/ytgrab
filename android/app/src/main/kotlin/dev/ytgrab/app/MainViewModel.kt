package dev.ytgrab.app

import android.app.Application
import android.content.Context
import android.graphics.BitmapFactory
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.runtime.snapshotFlow
import androidx.core.content.edit
import androidx.compose.ui.graphics.ImageBitmap
import androidx.compose.ui.graphics.asImageBitmap
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.drop
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL

enum class Mode(val key: String) { VIDEO("video"), AUDIO("audio"), MP3("mp3"), TRANSCRIPT("transcript") }

/**
 * A transcript track. kind is "manual" (written by people), "original"
 * (YouTube's automatic one in the language spoken) or "translated"; see
 * _transcripts() in ytgrab/core.py.
 */
data class Transcript(val code: String, val auto: Boolean, val kind: String = "") {
    companion object {
        /** Each video's own language, for several videos at once (core.ORIGINAL). */
        const val ORIGINAL = "orig"
    }
}

data class PlaylistEntry(val url: String, val title: String)

data class Playlist(val title: String, val uploader: String, val entries: List<PlaylistEntry>)

data class VideoInfo(
    val title: String,
    val uploader: String,
    val duration: Int,
    val thumbnail: String,
    /** Best first; the best-ranked ones don't always exist, so each is tried in turn. */
    val thumbnails: List<String>,
    val heights: List<Int>,
    val isLive: Boolean,
    val transcripts: List<Transcript>,
    /** False for a link to a playlist alone; the details are then the playlist's. */
    val video: Boolean,
    /** The playlist the link names, if it names one. */
    val playlist: Playlist?,
) {
    companion object {
        private fun strings(array: JSONArray?) = array?.let { list -> List(list.length()) { list.getString(it) } }.orEmpty()

        fun from(json: JSONObject): VideoInfo {
            val heights = json.getJSONArray("heights")
            val tracks = json.getJSONArray("transcripts")
            val list = json.optJSONObject("playlist")
            return VideoInfo(
                title = json.optString("title"),
                uploader = json.optString("uploader"),
                duration = json.optInt("duration"),
                thumbnail = json.optString("thumbnail"),
                thumbnails = strings(json.optJSONArray("thumbnails")),
                heights = List(heights.length()) { heights.getInt(it) },
                isLive = json.optBoolean("is_live"),
                transcripts = List(tracks.length()) {
                    val t = tracks.getJSONObject(it)
                    Transcript(t.getString("code"), t.optBoolean("auto"), t.optString("kind"))
                },
                video = json.optBoolean("video", true),
                playlist = list?.let {
                    val entries = it.getJSONArray("entries")
                    Playlist(
                        title = it.optString("title"),
                        uploader = it.optString("uploader"),
                        entries = List(entries.length()) { i ->
                            val entry = entries.getJSONObject(i)
                            PlaylistEntry(entry.getString("url"), entry.optString("title"))
                        },
                    )
                },
            )
        }
    }
}

/** The same rules as find_links() in ytgrab/core.py. */
object Links {
    private val LINK = Regex("""https?://[^\s<>"']+""")

    /** Every link in shared or pasted text, once each and in order. */
    fun find(text: String): List<String> =
        LINK.findAll(text).map { it.value.trimEnd('.', ',', ';', ':', '!', '?', ')', ']', '}') }.distinct().toList()

    /** Offered when the videos aren't known one by one; each is a ceiling. */
    val STANDARD_HEIGHTS = listOf(2160, 1440, 1080, 720, 480, 360)
}

class MainViewModel(app: Application) : AndroidViewModel(app) {
    // The choices below are remembered between launches, like the desktop app's.
    private val prefs = app.getSharedPreferences("choices", Context.MODE_PRIVATE)

    var url by mutableStateOf("")
    var fetching by mutableStateOf(false)
        private set
    var info by mutableStateOf<VideoInfo?>(null)
        private set
    var thumbnail by mutableStateOf<ImageBitmap?>(null)
        private set
    var message by mutableStateOf<String?>(null)

    var mode by mutableStateOf(Mode.entries.firstOrNull { it.key == prefs.getString("mode", null) } ?: Mode.VIDEO)
    /** The resolution picked, a ceiling: a video without it gets the highest one under it. */
    var height by mutableStateOf(saved("height", "best") { it == "best" || it.toIntOrNull() != null })
    var container by mutableStateOf(saved("container", "mp4") { it in listOf("mp4", "mkv") })
    var audioStream by mutableStateOf(saved("audio_stream", "best") { it in listOf("best", "opus", "m4a") })
    var bitrate by mutableStateOf(saved("mp3_quality", "192") { it in listOf("0", "320", "256", "192", "128") })
    var transcriptLang by mutableStateOf<String?>(null)
    var transcriptFormat by mutableStateOf(saved("transcript_format", "txt") { it in listOf("txt", "srt", "vtt") })
    var embed by mutableStateOf(prefs.getBoolean("embed", true))

    /** A newer release, until it's installed or put off. */
    var update by mutableStateOf<Update?>(null)
        private set
    /** How far the update's download has got, 0 to 1, while it runs. */
    var updateProgress by mutableStateOf<Float?>(null)
        private set
    var updateError by mutableStateOf<String?>(null)
        private set
    private var updateJob: Job? = null

    // "Only a part": the times stay as typed, the switch decides if they count.
    var partOn by mutableStateOf(false)
    var partFrom by mutableStateOf("")
    var partTo by mutableStateOf("")

    /** For a video in a playlist: take the whole list rather than the video. */
    var wholePlaylist by mutableStateOf(false)

    // The link the details on screen were read from.
    private var infoUrl by mutableStateOf("")

    private var fetchJob: Job? = null

    init {
        // Python takes a moment to start the first time; do it before it's needed.
        viewModelScope.launch { runCatching { Engine.warmUp(getApplication()) } }
        // Each choice is saved as soon as it's made.
        viewModelScope.launch {
            snapshotFlow { listOf(mode.key, height, container, audioStream, bitrate, transcriptFormat, embed) }
                .drop(1)
                .collect {
                    prefs.edit {
                        putString("mode", mode.key)
                        putString("height", height)
                        putString("container", container)
                        putString("audio_stream", audioStream)
                        putString("mp3_quality", bitrate)
                        putString("transcript_format", transcriptFormat)
                        putBoolean("embed", embed)
                    }
                }
        }
        // A quiet look for a newer release; no network is no news.
        viewModelScope.launch { update = runCatching { Updates.check() }.getOrNull() }
    }

    private fun saved(key: String, default: String, valid: (String) -> Boolean): String =
        prefs.getString(key, null)?.takeIf(valid) ?: default

    /** Download the update, then hand it to Android's installer. */
    fun installUpdate() {
        val release = update ?: return
        if (updateJob?.isActive == true) return
        updateError = null
        updateProgress = 0f
        updateJob = viewModelScope.launch {
            try {
                val apk = Updates.download(getApplication(), release) { updateProgress = it }
                Updates.install(getApplication(), apk)
            } catch (e: kotlinx.coroutines.CancellationException) {
                throw e
            } catch (e: Exception) {
                updateError = e.localizedMessage ?: e.toString()
            } finally {
                updateProgress = null
            }
        }
    }

    fun dismissUpdate() {
        updateJob?.cancel()
        update = null
        updateError = null
    }

    /** The links in the box when there are several; empty for one or none. */
    val links: List<String>
        get() = Links.find(url).takeIf { it.size > 1 }.orEmpty()

    /** The details read for the link in the box, if they're for that link. */
    val shown: VideoInfo?
        get() = info?.takeIf { links.isEmpty() && infoUrl == singleLink() }

    private fun singleLink(): String = Links.find(url).firstOrNull() ?: url.trim()

    /** A shared "Watch this: https://youtu.be/..." becomes just the link; several links stay together. */
    fun onShared(text: String) {
        val found = Links.find(text)
        if (found.size > 1) {
            url = found.joinToString(" ")
            message = null
            return
        }
        url = found.firstOrNull() ?: text.trim()
        fetch()
    }

    fun fetch() {
        val link = singleLink()
        if (link.isEmpty() || links.isNotEmpty() || fetchJob?.isActive == true) return
        fetching = true
        message = null
        fetchJob = viewModelScope.launch {
            try {
                val result = Engine.fetchInfo(getApplication(), link)
                if (result.optBoolean("ok")) {
                    show(link, VideoInfo.from(result.getJSONObject("info")))
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

    private fun show(link: String, video: VideoInfo) {
        info = video
        infoUrl = link
        thumbnail = null
        // Times typed for one video rarely fit the next, so it starts whole;
        // the link names this video, so the list is the option.
        partOn = false
        wholePlaylist = false
        transcriptLang = defaultTranscript(video.transcripts)
        val candidates = video.thumbnails.ifEmpty { listOf(video.thumbnail) }.filter { it.isNotEmpty() }
        if (candidates.isNotEmpty()) {
            viewModelScope.launch {
                val image = candidates.firstNotNullOfOrNull { loadImage(it) }
                // A slower load for an earlier video mustn't land on this one.
                if (info === video) thumbnail = image
            }
        }
    }

    /**
     * The interface language first, then English, then whatever is listed
     * first. The list comes best first, so "en-orig" wins over a translated "en".
     */
    private fun defaultTranscript(tracks: List<Transcript>): String? {
        val wanted = listOf(Engine.language(getApplication()), "en")
        for (lang in wanted) {
            tracks.firstOrNull { it.code == lang || it.code.substringBefore('-') == lang }?.let { return it.code }
        }
        return tracks.firstOrNull()?.code
    }

    /** Whether Download takes the playlist the link names rather than one video. */
    val takesPlaylist: Boolean
        get() {
            val video = shown ?: return false
            return video.playlist != null && (!video.video || wholePlaylist)
        }

    /** How many downloads the button adds: several links, a playlist, or one. */
    val count: Int
        get() = when {
            links.isNotEmpty() -> links.size
            takesPlaylist -> shown?.playlist?.entries?.size ?: 1
            else -> 1
        }

    /** Resolutions to offer: the video's own, or the standard ceilings until one is read. */
    val heights: List<Int>
        get() = shown?.heights ?: Links.STANDARD_HEIGHTS

    /** The offered resolution for the one picked: the same, or the highest under it. */
    val heightShown: String
        get() {
            val wanted = height.toIntOrNull() ?: return "best"
            return heights.filter { it <= wanted }.maxOrNull()?.toString() ?: "best"
        }

    /** Transcript languages to offer; several links get each video's own, the interface language and English. */
    val transcripts: List<Transcript>?
        get() = if (links.isNotEmpty()) {
            listOf(Transcript(Transcript.ORIGINAL, true, "original")) +
                listOf(Engine.language(getApplication()), "en").distinct().map { Transcript(it, false) }
        } else {
            shown?.transcripts
        }

    /** Whether "Only a part" can be offered: one read video that isn't live. */
    val partAvailable: Boolean
        get() = shown?.isLive == false && mode != Mode.TRANSCRIPT && !takesPlaylist

    /** What the part fields come to, or null while the whole video is wanted. */
    fun partCheck(): PartCheck? {
        val video = shown ?: return null
        if (!partOn || !partAvailable) return null
        return Parts.check(partFrom, partTo, video.duration)
    }

    /** What the Download button should queue, or null if something is missing. */
    fun requests(): List<DownloadRequest>? {
        val link = singleLink().takeIf { it.isNotEmpty() } ?: return null
        val title = shown?.takeIf { it.video }?.title.orEmpty()
        val part = when (val check = partCheck()) {
            null -> null
            is PartCheck.Valid -> check.part
            else -> return null  // the fields say what's wrong
        }
        val one = when (mode) {
            Mode.VIDEO -> DownloadRequest(link, title, "video", heightShown, container, embed, part)
            Mode.AUDIO -> DownloadRequest(link, title, "audio", audioStream, "mp4", embed, part)
            Mode.MP3 -> DownloadRequest(link, title, "mp3", bitrate, "mp4", embed, part)
            Mode.TRANSCRIPT -> {
                val offered = transcripts.orEmpty()
                val lang = transcriptLang?.takeIf { code -> offered.any { it.code == code } }
                    ?: defaultTranscript(offered) ?: return null
                DownloadRequest(link, title, "transcript", lang, transcriptFormat, false)
            }
        }
        return when {
            links.isNotEmpty() -> links.map { one.copy(url = it, title = "") }
            takesPlaylist -> shown?.playlist?.entries?.map { one.copy(url = it.url, title = it.title) }
            else -> listOf(one)
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
}
