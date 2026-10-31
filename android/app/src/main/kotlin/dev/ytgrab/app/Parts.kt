package dev.ytgrab.app

import java.util.Locale

/** A stretch of the video to download instead of all of it; end is null for "to the end". */
data class Part(val start: Int, val end: Int?)

/** What the From and To fields come to: a part to download, or why they don't make one. */
sealed interface PartCheck {
    data class Valid(val part: Part) : PartCheck
    data class BadTime(val text: String) : PartCheck
    data object Empty : PartCheck
    data class StartsLate(val duration: Int) : PartCheck
    data object Backwards : PartCheck
}

/** The same rules as parse_time() and parse_section() in ytgrab/core.py. */
object Parts {
    private val TIME = Regex("[0-9]+(?:[:.,][0-9]+){0,2}")

    /**
     * "16:15" -> 975, "1:02:03" -> 3723, "75" -> 75, "" -> null. A dot or comma
     * works like a colon, as a phone's number pad has no colon. Whole seconds
     * only; throws IllegalArgumentException for anything else.
     */
    fun parseTime(text: String): Int? {
        val compact = text.filterNot { it.isWhitespace() }
        if (compact.isEmpty()) return null
        require(TIME.matches(compact)) { compact }
        val fields = compact.split(':', '.', ',').map { it.toLongOrNull() ?: -1L }
        // Only the leading field may run past 59: "90:00" is fine, "1:75" a typo.
        require(fields.first() in 0..1_000_000 && fields.drop(1).all { it in 0..59 }) { compact }
        val seconds = fields.fold(0L) { total, field -> total * 60 + field }
        // A million hours would wrap round to a negative time.
        require(seconds <= Int.MAX_VALUE) { compact }
        return seconds.toInt()
    }

    /**
     * An empty From is the beginning and an empty To the end; an end past the
     * end of the video is the end. duration is 0 when it isn't known.
     */
    fun check(from: String, to: String, duration: Int): PartCheck {
        val start = try {
            parseTime(from)
        } catch (e: IllegalArgumentException) {
            return PartCheck.BadTime(from.trim())
        }
        var end = try {
            parseTime(to)
        } catch (e: IllegalArgumentException) {
            return PartCheck.BadTime(to.trim())
        }
        if (start == null && end == null) return PartCheck.Empty
        val begin = start ?: 0
        if (duration > 0) {
            if (begin >= duration) return PartCheck.StartsLate(duration)
            if (end == null || end > duration) end = duration
        }
        if (end != null && end <= begin) return PartCheck.Backwards
        return PartCheck.Valid(Part(begin, end))
    }

    /** 975 -> "16:15", 3723 -> "1:02:03", 0 -> "0:00". */
    fun format(seconds: Int): String {
        val h = seconds / 3600
        val m = seconds % 3600 / 60
        val s = seconds % 60
        return if (h > 0) "%d:%02d:%02d".format(Locale.ROOT, h, m, s) else "%d:%02d".format(Locale.ROOT, m, s)
    }
}
