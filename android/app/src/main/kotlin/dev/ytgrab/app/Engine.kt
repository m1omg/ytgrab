package dev.ytgrab.app

import android.content.Context
import com.chaquo.python.PyObject
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.io.File

/**
 * The Python download engine - the same ytgrab/core.py the desktop app runs -
 * reached through the ytgrab_android bridge module.
 */
object Engine {
    private val startLock = Mutex()

    @Volatile
    private var bridge: PyObject? = null

    private suspend fun bridge(context: Context): PyObject {
        bridge?.let { return it }
        return startLock.withLock {
            bridge ?: withContext(Dispatchers.IO) {
                val app = context.applicationContext
                if (!Python.isStarted()) Python.start(AndroidPlatform(app))
                Python.getInstance().getModule("ytgrab_android").also {
                    it.callAttr(
                        "setup",
                        app.applicationInfo.nativeLibraryDir,
                        app.cacheDir.absolutePath,
                        language(app),
                    )
                    bridge = it
                }
            }
        }
    }

    /** Starts Python ahead of time, so the first fetch doesn't wait for it. */
    suspend fun warmUp(context: Context) {
        bridge(context)
    }

    suspend fun fetchInfo(context: Context, url: String): JSONObject = withContext(Dispatchers.IO) {
        val engine = bridge(context)
        engine.callAttr("set_language", language(context))
        JSONObject(engine.callAttr("fetch_info", url).toString())
    }

    suspend fun download(
        context: Context,
        request: DownloadRequest,
        destDir: File,
        listener: DownloadListener,
    ): JSONObject = withContext(Dispatchers.IO) {
        val engine = bridge(context)
        engine.callAttr("set_language", language(context))
        val result = engine.callAttr(
            "download", request.url, destDir.absolutePath, request.mode, request.quality,
            request.container, request.embed, listener,
            request.part?.start ?: -1, request.part?.end ?: -1,
        )
        JSONObject(result.toString())
    }

    /** The app's current language, which Android may set per app. */
    fun language(context: Context): String =
        context.resources.configuration.locales[0].language
}
