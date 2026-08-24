"""Download engine shared by the desktop app and the web app.

Everything that talks to yt-dlp lives here; the UIs only supply a request and
receive progress callbacks.
"""

import os
import re
import shutil
import sys
import uuid
from pathlib import Path
from urllib.parse import urlparse

from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError

from . import i18n
from .i18n import t

MODES = ("video", "audio", "mp3")
CONTAINERS = ("mp4", "mkv")

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
# helpers
# --------------------------------------------------------------------------

def is_supported_url(url):
    """Only real http(s) URLs, so yt-dlp can't be pointed at local files."""
    try:
        parsed = urlparse((url or "").strip())
    except ValueError:
        return False
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


def clean_error(message, lang=None):
    """Turn a yt-dlp exception into something worth showing a user.

    The engine itself raises in English so the strings stay greppable against
    yt-dlp's own output; the translation happens here, on the way to the UI.
    """
    message = re.sub(r"\x1b\[[0-9;]*m", "", str(message))
    message = message.replace("ERROR: ", "").strip()
    if "Sign in to confirm" in message or "not a bot" in message:
        return t("err_bot", lang)
    if "Video unavailable" in message:
        return t("err_unavailable", lang)
    if "is not a valid URL" in message or "Unsupported URL" in message:
        return t("err_unsupported", lang)
    if "No downloadable video found" in message:
        return t("err_no_video", lang)
    if "produced no output file" in message:
        return t("err_no_output", lang)
    return message[:600]


def base_opts():
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
    }
    location = ffmpeg_location()
    if location:
        opts["ffmpeg_location"] = location
    return opts


def fetch_info(url):
    """Read metadata without downloading. Raises DownloadError on failure."""
    opts = base_opts()
    opts["skip_download"] = True
    with YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)

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
    return {
        "title": info.get("title") or "",
        "uploader": info.get("uploader") or info.get("channel") or "",
        "duration": info.get("duration") or 0,
        "thumbnail": info.get("thumbnail") or "",
        "heights": heights,
        "audio_codecs": audio_codecs,
        "is_live": bool(info.get("is_live")),
    }


def build_opts(out_dir, mode, quality, container="mp4", embed_thumbnail=True,
               progress_hook=None, postprocessor_hook=None):
    """Translate a download request into yt-dlp options."""
    if mode not in MODES:
        raise ValueError("unknown mode: %r" % mode)
    if container not in CONTAINERS:
        raise ValueError("unknown container: %r" % container)

    opts = base_opts()
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

    else:  # mp3
        opts["format"] = "bestaudio/best"
        postprocessors.append({
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            # "0" means LAME VBR V0, anything else is a CBR kbps target.
            "preferredquality": str(quality),
        })

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
             progress_hook=None, postprocessor_hook=None):
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
                          progress_hook, postprocessor_hook)
        with YoutubeDL(opts) as ydl:
            ydl.extract_info(url, download=True)

        produced = find_output_file(work_dir)
        if produced is None:
            raise RuntimeError("yt-dlp finished but produced no output file.")

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
