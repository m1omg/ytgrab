"""Download engine shared by the desktop app and the web app.

Everything that talks to yt-dlp lives here; the UIs only supply a request and
receive progress callbacks.
"""

import html
import os
import re
import shutil
import sys
import textwrap
import time
import uuid
from pathlib import Path
from urllib.parse import urlparse

from yt_dlp import YoutubeDL
from yt_dlp.cookies import CookieLoadError
from yt_dlp.utils import DownloadError

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
    """
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


# --------------------------------------------------------------------------
# JavaScript runtime
# --------------------------------------------------------------------------

def bundled_qjs():
    """The QuickJS binary shipped inside a packaged build, or None."""
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


def _extract(url, opts, download, work_dir=None):
    """Run yt-dlp, trying other routes when YouTube stops it.

    Retries only on a bot check or a refused stream; anything else, a cancel
    included, ends it at once. If every route fails, the defaults' error is
    the one reported - a fallback failing for an unrelated reason (no IPv4
    route, say) would only hide it.
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
                info = ydl.extract_info(url, download=download)
        except DownloadError as exc:
            if isinstance((exc.exc_info or (None, None))[1], CookieLoadError):
                raise LoginReadError(opts["cookiesfrombrowser"][0], _plain(exc)) from exc
            if not overrides:
                default_error = exc
            # A preferred fallback failing says nothing about the defaults, so
            # they still get their turn - some videos only play through them.
            preferred = overrides and first is None
            if not (_is_forbidden(exc) or _is_bot_check(exc) or preferred):
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
               progress_hook=None, postprocessor_hook=None, cookies_browser=None):
    """Translate a download request into yt-dlp options."""
    if mode not in MODES:
        raise ValueError("unknown mode: %r" % mode)
    if mode == "transcript":
        if container not in TRANSCRIPT_FORMATS:
            raise ValueError("unknown transcript format: %r" % container)
    elif container not in CONTAINERS:
        raise ValueError("unknown container: %r" % container)

    opts = base_opts(cookies_browser)
    opts["outtmpl"] = str(Path(out_dir) / "%(title)s.%(ext)s")
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


def download(url, dest_dir, mode, quality, container="mp4", embed_thumbnail=True,
             progress_hook=None, postprocessor_hook=None, cookies_browser=None):
    """Download into dest_dir and return the finished file's Path.

    Work happens in a scratch directory inside dest_dir so the final move is a
    rename on the same filesystem rather than a copy of a multi-gigabyte file.
    """
    dest_dir = Path(dest_dir).expanduser()
    dest_dir.mkdir(parents=True, exist_ok=True)
    work_dir = dest_dir / (".ytgrab-tmp-" + uuid.uuid4().hex[:8])
    work_dir.mkdir()

    try:
        opts = build_opts(work_dir, mode, quality, container, embed_thumbnail,
                          progress_hook, postprocessor_hook, cookies_browser)
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
