package dev.ytgrab.app

import android.content.Context
import android.content.Intent
import androidx.core.content.FileProvider
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.io.File
import java.io.IOException
import java.net.HttpURLConnection
import java.net.URL
import java.security.MessageDigest

/** A newer release on GitHub, and the APK in it that fits this phone. */
data class Update(
    val version: String,
    val apkUrl: String,
    val size: Long,
    /** Lower-case hex, or empty when GitHub didn't give one. */
    val sha256: String,
)

/** The same checks as ytgrab/updater.py: GitHub's newest release, verified before it's installed. */
object Updates {
    private const val LATEST = "https://api.github.com/repos/m1omg/ytgrab/releases/latest"

    /** The release to update to, or null when this one is the newest. Throws when GitHub can't be reached. */
    suspend fun check(): Update? = withContext(Dispatchers.IO) {
        val connection = open(LATEST, "application/vnd.github+json")
        val json = try {
            connection.inputStream.use { JSONObject(it.reader().readText()) }
        } finally {
            connection.disconnect()
        }
        val version = json.getString("tag_name").trim().removePrefix("v")
        if (!newer(version, BuildConfig.VERSION_NAME)) return@withContext null
        // The APK built for the same phones as this one: arm64, arm32 or universal.
        val wanted = "ytgrab-android-${BuildConfig.FLAVOR}.apk"
        val assets = json.getJSONArray("assets")
        val asset = (0 until assets.length()).map(assets::getJSONObject)
            .firstOrNull { it.optString("name") == wanted } ?: return@withContext null
        Update(
            version = version,
            apkUrl = asset.getString("browser_download_url"),
            size = asset.optLong("size"),
            sha256 = asset.optString("digest").takeIf { it.startsWith("sha256:") }
                ?.removePrefix("sha256:")?.lowercase().orEmpty(),
        )
    }

    /** Whether version is later than current: 1.10.0 > 1.9.9, and 1.5 = 1.5.0. */
    fun newer(version: String, current: String): Boolean {
        fun parts(text: String): List<Int>? {
            val numbers = text.split(".").map { it.toIntOrNull() }
            return if (null in numbers) null else numbers.filterNotNull()
        }
        val a = parts(version) ?: return false
        val b = parts(current) ?: return true
        for (i in 0 until maxOf(a.size, b.size)) {
            val x = a.getOrElse(i) { 0 }
            val y = b.getOrElse(i) { 0 }
            if (x != y) return x > y
        }
        return false
    }

    /** Fetch the APK into the app's cache, making sure it arrived whole. */
    suspend fun download(context: Context, update: Update, progress: (Float) -> Unit): File =
        withContext(Dispatchers.IO) {
            val dir = File(context.cacheDir, "updates").apply { mkdirs() }
            dir.listFiles()?.forEach { it.delete() }
            val apk = File(dir, "ytgrab-${update.version}.apk")
            val digest = MessageDigest.getInstance("SHA-256")
            var done = 0L
            try {
                val connection = open(update.apkUrl, "application/octet-stream")
                try {
                    val total = update.size.takeIf { it > 0 } ?: connection.contentLengthLong
                    connection.inputStream.use { input ->
                        apk.outputStream().use { output ->
                            val buffer = ByteArray(256 * 1024)
                            while (true) {
                                ensureActive()
                                val read = input.read(buffer)
                                if (read < 0) break
                                output.write(buffer, 0, read)
                                digest.update(buffer, 0, read)
                                done += read
                                if (total > 0) progress(done.toFloat() / total)
                            }
                        }
                    }
                } finally {
                    connection.disconnect()
                }
                if (update.size > 0 && done != update.size) {
                    throw IOException(context.getString(R.string.update_incomplete))
                }
                val hex = digest.digest().joinToString("") { "%02x".format(it) }
                if (update.sha256.isNotEmpty() && hex != update.sha256) {
                    throw IOException(context.getString(R.string.update_corrupt))
                }
            } catch (e: Throwable) {
                apk.delete()
                throw e
            }
            apk
        }

    /**
     * Hand the APK to Android's installer. It asks before replacing the app,
     * and the first time also asks to allow ytgrab to install apps.
     */
    fun install(context: Context, apk: File) {
        val uri = FileProvider.getUriForFile(context, "${context.packageName}.files", apk)
        val intent = Intent(Intent.ACTION_VIEW)
            .setDataAndType(uri, "application/vnd.android.package-archive")
            .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_ACTIVITY_NEW_TASK)
        context.startActivity(intent)
    }

    private fun open(address: String, accept: String): HttpURLConnection =
        (URL(address).openConnection() as HttpURLConnection).apply {
            connectTimeout = 20_000
            readTimeout = 30_000
            setRequestProperty("Accept", accept)
            setRequestProperty("User-Agent", "ytgrab/${BuildConfig.VERSION_NAME}")
            if (responseCode !in 200..299) throw IOException("HTTP $responseCode")
        }
}
