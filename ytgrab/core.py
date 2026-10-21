"""Download engine shared by the desktop app and the web app.

Everything that talks to yt-dlp lives here; the UIs only supply a request and
receive progress callbacks.
"""

import contextlib
import functools
import html
import os
import re
import shutil
import subprocess
import sys
import textwrap
import threading
import time
import uuid
from pathlib import Path
from urllib.parse import urlparse

from yt_dlp import YoutubeDL
from yt_dlp.cookies import CookieLoadError
from yt_dlp.postprocessor import get_postprocessor
from yt_dlp.postprocessor.common import PostProcessor
from yt_dlp.postprocessor.ffmpeg import FFmpegPostProcessor
from yt_dlp.utils import DownloadError, Popen, download_range_func

from . import i18n
from .i18n import t

MODES = ("video", "audio", "mp3", "transcript")
CONTAINERS = ("mp4", "mkv")
# Transcript outputs. yt-dlp converts between srt/vtt/ass/lrc but has no plain
# text target, so txt is produced here by parsing the subtitle file instead -
# which also means txt needs no ffmpeg.
TRANSCRIPT_FORMATS = ("txt", "srt", "vtt")

# Browsers a YouTube login can be borrowed from, keyed by yt-dlp's names.
# Safari keeps its cookies somewhere yt-dlp can only read on macOS.
COOKIE_BROWSERS = {
    "firefox": "Firefox",
    "chrome": "Chrome",
    "chromium": "Chromium",
    "brave": "Brave",
    "edge": "Edge",
    "opera": "Opera",
    "vivaldi": "Vivaldi",
}
if sys.platform == "darwin":
    COOKIE_BROWSERS["safari"] = "Safari"

# Files yt-dlp leaves beside the real output (thumbnails, partial downloads).
_JUNK_SUFFIXES = {".part", ".ytdl", ".temp", ".jpg", ".png", ".webp", ".json", ".description"}


# --------------------------------------------------------------------------
# ffmpeg discovery
# --------------------------------------------------------------------------

def _make_executable(path):
    """PyInstaller can strip the exec bit off a bundled binary."""
    try:
        if not os.access(path, os.X_OK):
            os.chmod(path, os.stat(path).st_mode | 0o111)
    except OSError:
        pass
    return path


def ffmpeg_location():
    """Where yt-dlp should look for ffmpeg.

    A system ffmpeg wins because it ships ffprobe alongside it, which lets
    yt-dlp inspect streams properly. Otherwise fall back to the binary bundled
    by the imageio-ffmpeg wheel, so a packaged app never asks the user to
    install anything. Returns a directory or a single binary path, both of
    which yt-dlp accepts, or None if nothing is available.

    YTGRAB_FFMPEG_BIN names a binary that wins over all of these; the Android app
    uses it to hand over the ffmpeg it ships.
    """
    override = os.environ.get("YTGRAB_FFMPEG_BIN")
    if override and Path(override).is_file():
        return override

    system = shutil.which("ffmpeg")
    if system:
        return str(Path(system).parent)

    # Frozen build: ffmpeg is copied next to the bundled modules.
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        root = Path(meipass)
        for name in ("ffmpeg", "ffmpeg.exe"):
            candidate = root / name
            if candidate.is_file():
                return _make_executable(str(candidate))
        # Be forgiving about how the binary was staged into the bundle.
        for candidate in sorted(root.glob("ffmpeg*")):
            if candidate.is_file():
                return _make_executable(str(candidate))
            if candidate.is_dir():
                for inner in sorted(candidate.glob("ffmpeg*")):
                    if inner.is_file():
                        return _make_executable(str(inner))

    try:
        import imageio_ffmpeg
        return _make_executable(imageio_ffmpeg.get_ffmpeg_exe())
    except Exception:
        return None


def has_ffmpeg():
    return ffmpeg_location() is not None


def ffmpeg_binary():
    """The ffmpeg program itself, wherever ffmpeg_location() points."""
    location = ffmpeg_location()
    if location and Path(location).is_dir():
        return shutil.which("ffmpeg", path=location)
    return location


@functools.lru_cache(maxsize=None)
def ffmpeg_reads_https(binary):
    """Whether this ffmpeg can fetch a stream itself.

    Cutting a part out during the download needs that; a build without its
    network code can still cut a finished file.
    """
    try:
        out, _, _ = Popen.run([binary, "-hide_banner", "-protocols"], text=True,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
    except Exception:  # noqa: BLE001 - a broken ffmpeg shows up later anyway
        return False
    inputs = out.split("Output:")[0]
    return "https" in inputs.split()


# --------------------------------------------------------------------------
# JavaScript runtime
# --------------------------------------------------------------------------

def bundled_qjs():
    """The QuickJS binary shipped inside a packaged build, or None.

    YTGRAB_QJS_BIN names one directly, which is how the Android app passes its own.
    """
    override = os.environ.get("YTGRAB_QJS_BIN")
    if override and Path(override).is_file():
        return override
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        for name in ("qjs", "qjs.exe"):
            candidate = Path(meipass) / name
            if candidate.is_file():
                return _make_executable(str(candidate))
    return None


def js_runtimes():
    """JavaScript runtimes yt-dlp may use to solve YouTube's challenges.

    YouTube hides its stream URLs behind JavaScript challenges. Without a
    runtime to solve them yt-dlp is left with one fallback client, a mode it
    calls deprecated and in which formats go missing. yt-dlp picks the fastest
    runtime present - deno, then node, then QuickJS, then bun - so a system
    deno or node wins, and the QuickJS inside packaged builds covers every
    machine that has neither.
    """
    qjs = bundled_qjs()
    return {"deno": {}, "node": {}, "quickjs": {"path": qjs} if qjs else {}, "bun": {}}


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------

def is_supported_url(url):
    """Only real http(s) URLs, so yt-dlp can't be pointed at local files."""
    try:
        parsed = urlparse((url or "").strip())
    except ValueError:
        return False
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


class LoginReadError(DownloadError):
    """The YouTube login could not be read from the chosen browser."""

    def __init__(self, browser, reason):
        super().__init__(f"Could not read the YouTube login from {browser}: {reason}")
        self.browser, self.reason = browser, reason


def _plain(message):
    message = re.sub(r"\x1b\[[0-9;]*m", "", str(message))
    return message.replace("ERROR: ", "").strip()


def clean_error(message, lang=None, login=None):
    """Turn a yt-dlp exception into something worth showing a user.

    The engine itself raises in English so the strings stay greppable against
    yt-dlp's own output; the translation happens here, on the way to the UI.
    `login` is the browser the YouTube login was borrowed from, if any.
    """
    if isinstance(message, LoginReadError):
        return t("err_cookies", lang, browser=COOKIE_BROWSERS.get(message.browser, message.browser),
                 reason=message.reason[:300])
    message = _plain(message)
    if _BOT_CHECK.search(message):
        if login:
            return t("err_bot_login", lang, browser=COOKIE_BROWSERS.get(login, login))
        return t("err_bot", lang)
    if "Video unavailable" in message:
        return t("err_unavailable", lang)
    if "is not a valid URL" in message or "Unsupported URL" in message:
        return t("err_unsupported", lang)
    if "No downloadable video found" in message:
        return t("err_no_video", lang)
    if "No transcript available" in message:
        return t("err_no_transcript", lang)
    if "produced no output file" in message:
        return t("err_no_output", lang)
    return message[:600]


_TAG_RE = re.compile(r"<[^>]*>")
_TIMESTAMP_RE = re.compile(r"\d{1,2}:\d{2}:\d{2}[.,]\d{3}\s*-->")
_CUE_HEADERS = ("WEBVTT", "Kind:", "Language:", "NOTE", "STYLE", "REGION")


def subtitles_to_text(path, width=80):
    """Flatten an srt or vtt file into readable plain text.

    Auto-generated captions scroll: every cue repeats the tail of the one
    before it, so consecutive duplicate lines are dropped. Timings are
    discarded on purpose - srt and vtt stay available when they are wanted.
    """
    lines = Path(path).read_text(encoding="utf-8", errors="replace").splitlines()
    out = []
    for index, line in enumerate(lines):
        line = line.strip()
        if not line or line.startswith(_CUE_HEADERS) or _TIMESTAMP_RE.search(line):
            continue
        # A cue number or identifier is whatever sits just above a timestamp.
        following = lines[index + 1].strip() if index + 1 < len(lines) else ""
        if _TIMESTAMP_RE.search(following):
            continue
        # Tags go before entities, so that an escaped &lt;word&gt; survives.
        # YouTube double-encodes apostrophes (&amp;#39;), hence unescaping twice.
        line = html.unescape(html.unescape(_TAG_RE.sub("", line))).strip()
        if line and (not out or out[-1] != line):
            out.append(line)
    text = re.sub(r"\s+", " ", " ".join(out)).strip()
    return textwrap.fill(text, width) + "\n" if text else ""


# --------------------------------------------------------------------------
# parts of a video
# --------------------------------------------------------------------------

_TIME_RE = re.compile(r"[0-9]+(?:[:.,][0-9]+){0,2}")


def parse_time(text):
    """'16:15' -> 975, '1:02:03' -> 3723, '75' -> 75, '' -> None.

    A dot or comma works like a colon (16.15), as clock times are often
    written that way and a phone's number pad has no colon. Whole seconds
    only. Raises ValueError for anything else.
    """
    text = re.sub(r"\s+", "", text or "")
    if not text:
        return None
    if not _TIME_RE.fullmatch(text):
        raise ValueError(text)
    parts = [int(part) for part in re.split(r"[:.,]", text)]
    # Only the leading field may run past 59: "90:00" is fine, "1:75" a typo.
    if any(part >= 60 for part in parts[1:]):
        raise ValueError(text)
    seconds = 0
    for part in parts:
        seconds = seconds * 60 + part
    return seconds


def format_time(seconds):
    """975 -> '16:15', 3723 -> '1:02:03', 0 -> '0:00'."""
    seconds = int(seconds)
    h, m, s = seconds // 3600, seconds % 3600 // 60, seconds % 60
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def parse_section(start_text, end_text, duration=0, lang=None):
    """The part typed into From and To, as (start, end) seconds.

    An empty From is the beginning and an empty To the end; an end past the
    end of the video is the end. end is None only when the length is unknown.
    Raises ValueError with a message to show the user.
    """
    try:
        start = parse_time(start_text)
    except ValueError:
        raise ValueError(t("part_bad_time", lang, text=start_text.strip())) from None
    try:
        end = parse_time(end_text)
    except ValueError:
        raise ValueError(t("part_bad_time", lang, text=end_text.strip())) from None
    if start is None and end is None:
        raise ValueError(t("part_empty", lang))
    start = start or 0
    duration = int(duration or 0)
    if duration:
        if start >= duration:
            raise ValueError(t("part_start_late", lang, length=format_time(duration)))
        if end is None or end > duration:
            end = duration
    if end is not None and end <= start:
        raise ValueError(t("part_order", lang))
    return start, end


def _stamp(seconds):
    """975 -> '16m15s', 3723 -> '1h02m03s': a time that fits in a file name."""
    seconds = int(seconds)
    h, m, s = seconds // 3600, seconds % 3600 // 60, seconds % 60
    return f"{h}h{m:02d}m{s:02d}s" if h else f"{m}m{s:02d}s"


def part_label(section):
    """What a part's file name ends with, e.g. '16m15s-16m45s'."""
    start, end = section
    return f"{_stamp(start)}-{_stamp(end) if end is not None else ''}"


def base_opts(cookies_browser=None):
    opts = {
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "noplaylist": True,
        "restrictfilenames": False,
        "windowsfilenames": True,
        "retries": 5,
        "fragment_retries": 5,
        "concurrent_fragment_downloads": 4,
        "js_runtimes": js_runtimes(),
    }
    location = ffmpeg_location()
    if location:
        opts["ffmpeg_location"] = location
    if cookies_browser:
        # Requests go out signed in, which is what YouTube's bot check asks for.
        opts["cookiesfrombrowser"] = (cookies_browser,)
    return opts


# --------------------------------------------------------------------------
# running yt-dlp
# --------------------------------------------------------------------------

# YouTube's bot check and a refused stream (HTTP 403) both depend on which
# player client asked; these clients often get through when the defaults are
# stopped. The last attempt adds IPv4, as a flagged IPv6 address ends the same
# way.
_FALLBACK_CLIENTS = ["tv", "web_embedded", "web_safari"]
_FALLBACK = {"extractor_args": {"youtube": {"player_client": _FALLBACK_CLIENTS}}}
_FALLBACK_IPV4 = {**_FALLBACK, "source_address": "0.0.0.0"}

# Once the fallback clients have got past a bot check, they go first for a
# while. The download that follows a bot-checked preview would otherwise hit
# the same check and pay for a wasted extraction before falling back again.
_PREFER_FALLBACK_SECONDS = 30 * 60
_prefer_fallback_until = 0.0

_BOT_CHECK = re.compile(r"Sign in to confirm|not a bot")


def _is_forbidden(exc):
    return "HTTP Error 403" in str(exc)


def _is_bot_check(exc):
    return bool(_BOT_CHECK.search(str(exc)))


# ffmpeg fetches a part itself and says nothing about why it failed, so a
# refused stream looks like any other failure.
def _is_ffmpeg_failure(exc):
    return "ffmpeg exited with code" in str(exc)


def _part_not_fetched(exc):
    """ffmpeg could not fetch the part; the whole video may still download."""
    return _is_ffmpeg_failure(exc) or "cannot be partially downloaded" in str(exc)


# The ffmpeg runs started by the current thread's download, so that a cancel
# can stop one: yt-dlp waits for ffmpeg without calling the progress hooks,
# which is where a cancel normally lands.
_running = threading.local()


def _track_ffmpeg_runs():
    try:
        from yt_dlp.downloader import external
    except ImportError:
        return
    base = getattr(external, "Popen", None)
    if base is None or getattr(base, "_ytgrab_tracked", False):
        return

    class TrackedPopen(base):
        _ytgrab_tracked = True

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            runs = getattr(_running, "processes", None)
            if runs is not None:
                runs.append(self)

    external.Popen = TrackedPopen


_track_ffmpeg_runs()


def _use_ffmpeg_for_parts(location):
    """Let yt-dlp hand a part to the ffmpeg at `location`.

    yt-dlp only cuts during the download if it finds ffmpeg by itself, which
    it does on PATH rather than at ffmpeg_location - its command line sets
    this instead. A bundled ffmpeg is never on PATH, so without this a part
    download would stop with "ffmpeg is not installed".
    """
    var = getattr(FFmpegPostProcessor, "_ffmpeg_location", None)
    if var is not None and location:
        var.set(location)


class _PartWatch:
    """Progress for a part ffmpeg is fetching, and a way to stop it.

    yt-dlp only reports back once ffmpeg is done, so the progress comes from
    ffmpeg's own progress file. It is handed to the progress hook the way
    yt-dlp would, and whatever the hook raises - a cancel - stops ffmpeg.
    """

    POLL_SECONDS = 0.5

    def __init__(self, hook, progress_file, length):
        self.hook, self.file, self.length = hook, Path(progress_file), length
        self.processes = []
        self.stopped = None      # what the hook raised, if it did
        self.finished = False    # yt-dlp has reported the part done
        self._done = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def __enter__(self):
        _running.processes = self.processes
        self._thread.start()
        return self

    def __exit__(self, *exc):
        _running.processes = None
        self._done.set()
        self._thread.join(timeout=5)

    def wrap(self, hook):
        """yt-dlp's own hook calls; once the part is done, this one goes quiet."""
        def wrapped(d):
            if d.get("status") == "finished":
                self.finished = True
            return hook(d)
        return wrapped

    def _read(self):
        """(seconds written, bytes written) from ffmpeg's newest report."""
        try:
            with open(self.file, "rb") as f:
                f.seek(0, os.SEEK_END)
                f.seek(max(0, f.tell() - 4096))
                tail = f.read().decode("ascii", "replace")
        except OSError:
            return None
        times = re.findall(r"^out_time_us=(\d+)", tail, re.M)
        sizes = re.findall(r"^total_size=(\d+)", tail, re.M)
        if not times or not sizes:
            return None
        return int(times[-1]) / 1_000_000, int(sizes[-1])

    def _run(self):
        began = None
        while not self._done.wait(self.POLL_SECONDS):
            if self.finished:
                return
            report = self._read()
            if report is None:
                began = None    # not started yet, or a retry cleared it
                continue
            seconds, size = report
            now = time.monotonic()
            began = began or now
            elapsed = now - began
            d = {"status": "downloading", "downloaded_bytes": size, "elapsed": elapsed,
                 "speed": size / elapsed if elapsed > 0 else None}
            fraction = min(seconds / self.length, 1.0) if self.length else 0
            if fraction >= 0.01 and size:
                d["total_bytes_estimate"] = size / fraction
                d["eta"] = elapsed / fraction - elapsed
            try:
                self.hook(d)
            except BaseException as exc:  # noqa: BLE001 - re-raised by download()
                self.stopped = exc
                for proc in list(self.processes):
                    try:
                        proc.kill()
                    except OSError:
                        pass
                return


def _attempts():
    if time.monotonic() < _prefer_fallback_until:
        return (_FALLBACK, {}, _FALLBACK_IPV4)
    return ({}, _FALLBACK, _FALLBACK_IPV4)


def _clear_dir(path):
    for entry in Path(path).iterdir():
        if entry.is_dir():
            shutil.rmtree(entry, ignore_errors=True)
        else:
            entry.unlink(missing_ok=True)


def _extract(url, opts, download, work_dir=None, stopped=None, setup=None):
    """Run yt-dlp, trying other routes when YouTube stops it.

    Retries only on a bot check or a refused stream - which, for a part
    ffmpeg fetches, is any ffmpeg failure; anything else, a cancel included,
    ends it at once. `stopped` says whether a cancel cut ffmpeg off, and
    `setup` gets each YoutubeDL before it runs. If every route fails, the
    defaults' error is the one reported - a fallback failing for an unrelated
    reason (no IPv4 route, say) would only hide it.
    """
    global _prefer_fallback_until
    first = default_error = None
    for overrides in _attempts():
        if first is not None and work_dir is not None:
            # A partial file from the refused stream must not be resumed with
            # bytes from a different one.
            _clear_dir(work_dir)
        try:
            with YoutubeDL({**opts, **overrides}) as ydl:
                if setup is not None:
                    setup(ydl)
                info = ydl.extract_info(url, download=download)
        except DownloadError as exc:
            if stopped is not None and stopped():
                raise
            if isinstance((exc.exc_info or (None, None))[1], CookieLoadError):
                raise LoginReadError(opts["cookiesfrombrowser"][0], _plain(exc)) from exc
            if not overrides:
                default_error = exc
            # A preferred fallback failing says nothing about the defaults, so
            # they still get their turn - some videos only play through them.
            preferred = overrides and first is None
            if not (_is_forbidden(exc) or _is_bot_check(exc) or _is_ffmpeg_failure(exc)
                    or preferred):
                if first is None:
                    raise
                break
            first = first or exc
            continue
        if not overrides:
            _prefer_fallback_until = 0.0
        elif first is not None and _is_bot_check(first):
            _prefer_fallback_until = time.monotonic() + _PREFER_FALLBACK_SECONDS
        return info
    raise default_error or first


def fetch_info(url, cookies_browser=None):
    """Read metadata without downloading. Raises DownloadError on failure."""
    opts = base_opts(cookies_browser)
    opts["skip_download"] = True
    info = _extract(url, opts, download=False)

    if info.get("_type") == "playlist":
        entries = [e for e in (info.get("entries") or []) if e]
        if not entries:
            raise DownloadError("No downloadable video found at that link.")
        info = entries[0]

    formats = info.get("formats") or []
    heights = sorted(
        {f["height"] for f in formats
         if f.get("height") and f.get("vcodec") not in (None, "none")},
        reverse=True,
    )
    audio_codecs = sorted(
        {f["acodec"].split(".")[0] for f in formats
         if f.get("acodec") not in (None, "none") and f.get("vcodec") in (None, "none")}
    )
    # Manual tracks first: a human wrote them, so they read better than ASR.
    manual = info.get("subtitles") or {}
    automatic = info.get("automatic_captions") or {}
    transcripts = ([{"code": c, "auto": False} for c in sorted(manual)]
                   + [{"code": c, "auto": True} for c in sorted(automatic)
                      if c not in manual])

    return {
        "title": info.get("title") or "",
        "uploader": info.get("uploader") or info.get("channel") or "",
        "duration": info.get("duration") or 0,
        "thumbnail": info.get("thumbnail") or "",
        "heights": heights,
        "audio_codecs": audio_codecs,
        "is_live": bool(info.get("is_live")),
        "transcripts": transcripts,
    }


def build_opts(out_dir, mode, quality, container="mp4", embed_thumbnail=True,
               progress_hook=None, postprocessor_hook=None, cookies_browser=None,
               section=None):
    """Translate a download request into yt-dlp options.

    section is (start, end) in seconds to fetch only that part; end may be
    None for the rest of the video.
    """
    if mode not in MODES:
        raise ValueError("unknown mode: %r" % mode)
    if mode == "transcript":
        if container not in TRANSCRIPT_FORMATS:
            raise ValueError("unknown transcript format: %r" % container)
    elif container not in CONTAINERS:
        raise ValueError("unknown container: %r" % container)

    opts = base_opts(cookies_browser)
    name = "%(title)s"
    if section and mode != "transcript":
        start, end = section
        name += f" ({part_label(section)})"
        opts["download_ranges"] = download_range_func(
            None, [(start, end if end is not None else float("inf"))])
        if mode in ("audio", "mp3"):
            # ffmpeg starts from the last seek point before the cut, seconds
            # early in a WebM; audio can start on the exact packet instead.
            # Video can't: it has to begin on a keyframe, which an MP4 then
            # hides up to the cut.
            opts["external_downloader_args"] = {"ffmpeg_o": ["-copypriorss", "0"]}
    opts["outtmpl"] = str(Path(out_dir) / f"{name}.%(ext)s")
    if progress_hook:
        opts["progress_hooks"] = [progress_hook]
    if postprocessor_hook:
        opts["postprocessor_hooks"] = [postprocessor_hook]

    postprocessors = []

    if mode == "video":
        height_filter = "" if quality in ("best", "", None) else "[height<=%d]" % int(quality)
        if container == "mp4":
            # Prefer streams that already fit MP4 so merging stays a remux.
            opts["format"] = (
                f"bestvideo{height_filter}[vcodec^=avc1][ext=mp4]+bestaudio[ext=m4a]/"
                f"bestvideo{height_filter}[ext=mp4]+bestaudio[ext=m4a]/"
                f"bestvideo{height_filter}+bestaudio/best{height_filter}/best"
            )
            opts["merge_output_format"] = "mp4"
        else:
            # MKV holds VP9/AV1 + Opus as-is, so nothing is ever re-encoded.
            opts["format"] = f"bestvideo{height_filter}+bestaudio/best{height_filter}/best"
            opts["merge_output_format"] = "mkv"

    elif mode == "audio":
        # Original stream, no transcode: preferredcodec="best" keeps the source
        # codec and only lifts it out of its container.
        if quality == "opus":
            opts["format"] = "bestaudio[acodec^=opus]/bestaudio/best"
        elif quality == "m4a":
            opts["format"] = "bestaudio[ext=m4a]/bestaudio/best"
        else:
            opts["format"] = "bestaudio/best"
        postprocessors.append({
            "key": "FFmpegExtractAudio",
            "preferredcodec": "best",
            "nopostoverwrites": False,
        })

    elif mode == "mp3":
        opts["format"] = "bestaudio/best"
        postprocessors.append({
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            # "0" means LAME VBR V0, anything else is a CBR kbps target.
            "preferredquality": str(quality),
        })

    else:  # transcript - subtitles only, no media stream is fetched
        opts["skip_download"] = True
        opts["writesubtitles"] = True
        opts["writeautomaticsub"] = True
        # A concrete language, never "all": YouTube offers automatic
        # translations into ~200 of them and would write a file for each.
        opts["subtitleslangs"] = [quality if quality and quality != "best" else "en"]
        # vtt is what YouTube serves, so asking for it avoids a conversion.
        opts["subtitlesformat"] = "vtt/srt/best"
        if container == "srt":
            postprocessors.append({"key": "FFmpegSubtitlesConvertor", "format": "srt"})

    if mode != "transcript":
        postprocessors.append({"key": "FFmpegMetadata", "add_metadata": True})

    if embed_thumbnail and mode in ("audio", "mp3"):
        opts["writethumbnail"] = True
        postprocessors.append({"key": "EmbedThumbnail", "already_have_thumbnail": False})

    opts["postprocessors"] = postprocessors
    return opts


def find_output_file(out_dir):
    """Pick the finished media file out of a job directory."""
    files = [p for p in Path(out_dir).iterdir()
             if p.is_file() and p.suffix.lower() not in _JUNK_SUFFIXES]
    if not files:
        return None
    # If a merge left its sources behind, the largest file is the real result.
    return max(files, key=lambda p: p.stat().st_size)


def unique_path(path):
    """Avoid clobbering an existing file: name.ext -> name (2).ext"""
    if not path.exists():
        return path
    stem, suffix, n = path.stem, path.suffix, 2
    while True:
        candidate = path.with_name(f"{stem} ({n}){suffix}")
        if not candidate.exists():
            return candidate
        n += 1


def _remux(path, args, what):
    """Run ffmpeg over a finished file with `args`, replacing it in place."""
    out = path.with_name(f"{path.stem}.{what}{path.suffix}")
    _, err, code = Popen.run(
        [ffmpeg_binary(), "-y", "-hide_banner", "-loglevel", "error", *args, str(out)],
        text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if code != 0 or not out.is_file():
        raise DownloadError(f"ffmpeg could not {what} the part: " + err.strip()[-300:])
    return out.replace(path)


def _starts_on_keyframe(path, info):
    """Whether a part's video can only start on the keyframe before the cut.

    An MP4 hides the frames before the cut; MKV and WebM have no way to.
    """
    return path.suffix.lower() in (".mkv", ".webm") and info.get("vcodec") not in (None, "none")


def _stream_starts(path):
    """When the first video and audio packets play, as {"video": s, "audio": s}.

    ffmpeg's frame checksums list every packet with its stream and time,
    which needs no ffprobe - the Android app has none.
    """
    out, _, _ = Popen.run(
        [ffmpeg_binary(), "-v", "error", "-copyts", "-i", str(path), "-map", "0", "-c", "copy",
         "-t", "60", "-f", "framemd5", "-"],
        text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    timebase, kind, starts = {}, {}, {}
    for line in out.splitlines():
        if line.startswith("#tb "):
            index, value = line[4:].split(":", 1)
            num, den = value.strip().split("/")
            timebase[int(index)] = int(num) / int(den)
        elif line.startswith("#media_type "):
            index, value = line[12:].split(":", 1)
            kind[int(index)] = value.strip()
        elif line and not line.startswith("#"):
            index = int(line.split(",")[0])
            if index in timebase and kind.get(index) not in (None, *starts):
                starts[kind[index]] = int(line.split(",")[2]) * timebase[index]
    return starts


def _align_start(path):
    """Start an MKV part's sound with its picture.

    Each stream starts at its own seek point before the cut, the audio's
    often seconds before the video's keyframe; that audio played over a
    black screen. It is dropped, so the part starts on its first picture.
    """
    starts = _stream_starts(path)
    video, audio = starts.get("video"), starts.get("audio")
    if video is None or audio is None or audio >= video - 0.02:
        return path
    # -ss counts from the file's start, which is the audio's.
    return _remux(path, ["-ss", f"{video - audio:.3f}", "-i", str(path),
                         "-map", "0", "-c", "copy", "-copypriorss:a", "0"], "align")


def _cut(path, section, exact_audio=True):
    """Keep only the part of a finished file, without re-encoding it.

    Video starts on the keyframe before the cut; audio starts on the exact
    packet, unless it has to start with a video that can't (see
    _starts_on_keyframe), and then _align_start() trims it.
    """
    start, end = section
    args = ["-ss", str(start), "-i", str(path)]
    if end is not None:
        args += ["-t", str(end - start)]
    args += ["-map", "0", "-c", "copy"]
    if exact_audio:
        args += ["-copypriorss:a", "0"]
    return _remux(path, args, "cut")


def _part_chapters(chapters, section):
    """The video's chapters as they fall in the part, timed from its start.

    Left as they are, they keep the whole video's length: an MP4 turns them
    into a track running to the video's end, and players show that length.
    """
    start, end = section
    kept = []
    for chapter in chapters or []:
        begin, finish = chapter.get("start_time"), chapter.get("end_time")
        if begin is None or (finish is not None and finish <= start) \
                or (end is not None and begin >= end):
            continue
        if end is not None:
            finish = end if finish is None else min(finish, end)
        kept.append({**chapter, "start_time": max(begin, start) - start,
                     "end_time": None if finish is None else finish - start})
    return kept


class PartFixupPP(PostProcessor):
    """Tidies a part ffmpeg has fetched: an MKV's sound and picture start
    together (see _align_start()) and the chapters fit (see _part_chapters())."""

    def __init__(self, downloader, section):
        super().__init__(downloader)
        self.section = section

    def run(self, info):
        path = Path(info["filepath"])
        if _starts_on_keyframe(path, info):
            _align_start(path)
        info["chapters"] = _part_chapters(info.get("chapters"), self.section)
        return [], info


class CutPP(PostProcessor):
    """Keeps only the part of a whole download; reported as the "Cut" stage."""

    def __init__(self, downloader, section):
        super().__init__(downloader)
        self.section = section

    def run(self, info):
        path = Path(info["filepath"])
        keyframe = _starts_on_keyframe(path, info)
        _cut(path, self.section, exact_audio=not keyframe)
        if keyframe:
            _align_start(path)
        info["chapters"] = _part_chapters(info.get("chapters"), self.section)
        return [], info


def _postprocessors_after(first, opts):
    """A setup for _extract() running first(ydl) before opts' postprocessors.

    yt-dlp puts postprocessors added later after the ones in the options;
    these have to see the file before anything converts it or writes its
    metadata.
    """
    def setup(ydl):
        ydl.add_post_processor(first(ydl))
        for pp_def in opts.get("postprocessors", []):
            pp_def = dict(pp_def)
            when = pp_def.pop("when", "post_process")
            ydl.add_post_processor(get_postprocessor(pp_def.pop("key"))(ydl, **pp_def), when=when)
    return setup


def _fetch_part(url, opts, work_dir, section, progress_hook):
    """Fetch only the part, or failing that the whole video and cut it here.

    ffmpeg fetches the part itself, which some builds can't and some servers
    refuse; the whole video then still gets the user their part.
    """
    location = ffmpeg_binary()
    if not location:
        raise DownloadError("Cutting out a part needs ffmpeg, which was not found.")
    _use_ffmpeg_for_parts(location)
    if ffmpeg_reads_https(location):
        start, end = section
        watch = None
        if progress_hook:
            report = work_dir / "ffmpeg-progress.temp"
            opts.setdefault("external_downloader_args", {}).setdefault("ffmpeg_o", []).extend(
                ["-progress", "file:" + str(report)])
            watch = _PartWatch(progress_hook, report, end - start if end is not None else None)
            opts["progress_hooks"] = [watch.wrap(progress_hook)]

        def stopped():
            return watch is not None and watch.stopped is not None

        fetch = {key: value for key, value in opts.items() if key != "postprocessors"}
        try:
            with watch or contextlib.nullcontext():
                _extract(url, fetch, download=True, work_dir=work_dir, stopped=stopped,
                         setup=_postprocessors_after(lambda ydl: PartFixupPP(ydl, section), opts))
        except DownloadError as exc:
            if stopped():
                raise watch.stopped from None
            if not _part_not_fetched(exc):
                raise
        else:
            if stopped():  # cancelled just as ffmpeg finished
                raise watch.stopped
            return find_output_file(work_dir)
        _clear_dir(work_dir)

    whole = {key: value for key, value in opts.items()
             if key not in ("download_ranges", "external_downloader_args", "postprocessors")}
    if progress_hook:
        whole["progress_hooks"] = [progress_hook]
    # The part comes out before anything converts the file, so an MP3
    # encodes thirty seconds rather than the whole hour.
    _extract(url, whole, download=True, work_dir=work_dir,
             setup=_postprocessors_after(lambda ydl: CutPP(ydl, section), opts))
    return find_output_file(work_dir)


def download(url, dest_dir, mode, quality, container="mp4", embed_thumbnail=True,
             progress_hook=None, postprocessor_hook=None, cookies_browser=None,
             section=None):
    """Download into dest_dir and return the finished file's Path.

    section (start, end) keeps only that part of the video; see build_opts().

    Work happens in a scratch directory inside dest_dir so the final move is a
    rename on the same filesystem rather than a copy of a multi-gigabyte file.
    """
    if mode == "transcript":
        section = None
    dest_dir = Path(dest_dir).expanduser()
    dest_dir.mkdir(parents=True, exist_ok=True)
    work_dir = dest_dir / (".ytgrab-tmp-" + uuid.uuid4().hex[:8])
    work_dir.mkdir()

    try:
        opts = build_opts(work_dir, mode, quality, container, embed_thumbnail,
                          progress_hook, postprocessor_hook, cookies_browser, section)
        if section:
            produced = _fetch_part(url, opts, work_dir, section, progress_hook)
        else:
            _extract(url, opts, download=True, work_dir=work_dir)
            produced = find_output_file(work_dir)
        if produced is None:
            if mode == "transcript":
                raise DownloadError("No transcript available in that language.")
            raise RuntimeError("yt-dlp finished but produced no output file.")

        if mode == "transcript" and container == "txt":
            flattened = produced.with_suffix(".txt")
            flattened.write_text(subtitles_to_text(produced), encoding="utf-8")
            produced.unlink()
            produced = flattened

        final = unique_path(dest_dir / produced.name)
        shutil.move(str(produced), str(final))
        return final
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


def default_download_dir():
    for candidate in (Path.home() / "Downloads", Path.home() / "Stiahnuté", Path.home()):
        if candidate.is_dir():
            return candidate
    return Path.home()


def format_size(num, lang=None):
    if not num:
        return ""
    for unit in ("B", "KB", "MB", "GB"):
        if num < 1024 or unit == "GB":
            return f"{i18n.number(num, 1, lang)} {unit}" if unit != "B" else f"{int(num)} B"
        num /= 1024
    return ""


def format_duration(seconds):
    if not seconds:
        return ""
    seconds = int(seconds)
    h, m, s = seconds // 3600, seconds % 3600 // 60, seconds % 60
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"
