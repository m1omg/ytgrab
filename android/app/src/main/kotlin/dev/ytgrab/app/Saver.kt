package dev.ytgrab.app

import android.content.ContentValues
import android.content.Context
import android.media.MediaScannerConnection
import android.os.Build
import android.os.Environment
import android.provider.MediaStore
import android.webkit.MimeTypeMap
import androidx.annotation.RequiresApi
import androidx.core.content.FileProvider
import java.io.File
import java.io.IOException

/** Moves a finished download into Download/ytgrab, where every file manager sees it. */
object Saver {
    private const val SUBDIR = "ytgrab"
    private val folder = "${Environment.DIRECTORY_DOWNLOADS}/$SUBDIR"

    // Types Android's own table doesn't know, or gets wrong for these files.
    private val knownTypes = mapOf(
        "mkv" to "video/x-matroska",
        "webm" to "video/webm",
        "mp4" to "video/mp4",
        "m4a" to "audio/mp4",
        "opus" to "audio/ogg",
        "ogg" to "audio/ogg",
        "mp3" to "audio/mpeg",
        "flac" to "audio/flac",
        "txt" to "text/plain",
        "srt" to "application/x-subrip",
        "vtt" to "text/vtt",
    )

    fun mimeFor(file: File): String {
        val ext = file.extension.lowercase()
        return knownTypes[ext]
            ?: MimeTypeMap.getSingleton().getMimeTypeFromExtension(ext)
            ?: "application/octet-stream"
    }

    fun save(context: Context, source: File): SavedFile =
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) saveToMediaStore(context, source)
        else saveToFolder(context, source)

    /** Android 10+: no storage permission needed. */
    @RequiresApi(Build.VERSION_CODES.Q)
    private fun saveToMediaStore(context: Context, source: File): SavedFile {
        val resolver = context.contentResolver
        val mime = mimeFor(source)
        val values = ContentValues().apply {
            put(MediaStore.MediaColumns.DISPLAY_NAME, source.name)
            put(MediaStore.MediaColumns.MIME_TYPE, mime)
            put(MediaStore.MediaColumns.RELATIVE_PATH, folder)
            put(MediaStore.MediaColumns.IS_PENDING, 1)
        }
        val uri = resolver.insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI, values)
            ?: throw IOException("Could not create ${source.name} in Downloads")
        try {
            val out = resolver.openOutputStream(uri)
                ?: throw IOException("Could not write ${source.name} to Downloads")
            out.use { stream -> source.inputStream().use { it.copyTo(stream) } }
            values.clear()
            values.put(MediaStore.MediaColumns.IS_PENDING, 0)
            resolver.update(uri, values, null, null)
        } catch (e: Exception) {
            resolver.delete(uri, null, null)
            throw e
        }
        // Android renames the file if the folder already has one by that name.
        val name = resolver.query(uri, arrayOf(MediaStore.MediaColumns.DISPLAY_NAME), null, null, null)
            ?.use { if (it.moveToFirst()) it.getString(0) else null } ?: source.name
        return SavedFile(uri, mime, "$folder/$name")
    }

    /** Android 7-9: a plain file, which needs the storage permission. */
    private fun saveToFolder(context: Context, source: File): SavedFile {
        @Suppress("DEPRECATION")
        val dir = File(Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_DOWNLOADS), SUBDIR)
        if (!dir.isDirectory && !dir.mkdirs()) throw IOException("Could not create $dir")
        var target = File(dir, source.name)
        var n = 2
        while (target.exists()) {
            val suffix = if (source.extension.isEmpty()) "" else ".${source.extension}"
            target = File(dir, "${source.nameWithoutExtension} ($n)$suffix")
            n++
        }
        source.copyTo(target)
        val mime = mimeFor(target)
        MediaScannerConnection.scanFile(context, arrayOf(target.path), arrayOf(mime), null)
        val uri = FileProvider.getUriForFile(context, "${context.packageName}.files", target)
        return SavedFile(uri, mime, "$folder/${target.name}")
    }
}
