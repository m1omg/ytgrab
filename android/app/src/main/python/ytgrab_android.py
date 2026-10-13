"""Bridge between the Android app and the ytgrab download engine.

Kotlin calls these functions through Chaquopy. Results and progress travel as
JSON strings so the Kotlin side never has to walk Python objects, and every
user-facing text is produced here with the same translations the desktop app
uses.
"""

import json
import os
import tempfile
import time

from ytgrab import core, i18n

# Progress reaches the UI at most this often, however fast yt-dlp reports it.
_PROGRESS_INTERVAL = 0.25


class Cancelled(Exception):
    """Raised inside a yt-dlp hook to stop a download."""


def setup(native_dir, cache_dir, lang):
    """Point the engine at the app's own ffmpeg and QuickJS, and its cache.

    Android only lets an app run files from its native library directory,
    which is where the build puts both helpers.
    """
    os.environ["YTGRAB_FFMPEG_BIN"] = os.path.join(native_dir, "libffmpeg.so")
    os.environ["YTGRAB_QJS_BIN"] = os.path.join(native_dir, "libqjs.so")
    # yt-dlp hands QuickJS its scripts as temporary files, and keeps a cache;
    # neither /tmp nor a home directory exists for an app.
    tmp = os.path.join(cache_dir, "tmp")
    os.makedirs(tmp, exist_ok=True)
    os.environ["TMPDIR"] = tmp
    tempfile.tempdir = tmp
    os.environ["XDG_CACHE_HOME"] = cache_dir
    set_language(lang)


def set_language(lang):
    i18n.set_language(i18n.normalise(lang) or i18n.DEFAULT_LANGUAGE)


def text(key, **fields):
    return i18n.t(key, **fields)


def versions():
    import yt_dlp
    from ytgrab import __version__
    return json.dumps({"ytgrab": __version__, "yt_dlp": yt_dlp.version.__version__})


def fetch_info(url):
    if not core.is_supported_url(url):
        return json.dumps({"ok": False, "error": i18n.t("invalid_link")})
    try:
        return json.dumps({"ok": True, "info": core.fetch_info(url)})
    except Exception as exc:  # noqa: BLE001 - every failure becomes a message
        return json.dumps({"ok": False, "error": core.clean_error(exc)})


def _stats(done, total, speed, eta):
    bits = []
    if total:
        bits.append(f"{core.format_size(done)} / {core.format_size(total)}")
    if speed:
        bits.append(f"{core.format_size(speed)}/s")
    if eta:
        bits.append(i18n.t("eta_left", time=core.format_duration(eta)))
    return "  ·  ".join(bits)


def _stage_text(name):
    key = f"stage_{name}"
    return i18n.t(key if key in i18n.STRINGS[i18n.DEFAULT_LANGUAGE] else "stage_processing")


def download(url, dest_dir, mode, quality, container, embed, listener):
    """Download into dest_dir, reporting to listener; returns a JSON result.

    listener is a Kotlin object with onProgress(json), onStage(text) and
    isCancelled(). The result is {"ok": true, "path": ...}, or {"ok": false}
    with either "cancelled": true or an "error" message.
    """
    last = [0.0]

    def on_progress(d):
        if listener.isCancelled():
            raise Cancelled()
        if d.get("status") == "downloading":
            now = time.monotonic()
            if now - last[0] < _PROGRESS_INTERVAL:
                return
            last[0] = now
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            done = d.get("downloaded_bytes") or 0
            percent = done / total * 100 if total else -1
            state = (i18n.t("downloading_percent", percent=i18n.number(percent))
                     if total else i18n.t("downloading"))
            listener.onProgress(json.dumps({
                "percent": percent,
                "state": state,
                "stats": _stats(done, total, d.get("speed") or 0, d.get("eta") or 0),
            }))
        elif d.get("status") == "finished":
            listener.onStage(i18n.t("stage_processing") + "…")

    def on_postprocess(d):
        if listener.isCancelled():
            raise Cancelled()
        if d.get("status") == "started":
            listener.onStage(_stage_text(d.get("postprocessor") or "") + "…")

    try:
        path = core.download(url, dest_dir, mode, quality, container, bool(embed),
                             progress_hook=on_progress, postprocessor_hook=on_postprocess)
        return json.dumps({"ok": True, "path": str(path)})
    except Cancelled:
        return json.dumps({"ok": False, "cancelled": True})
    except Exception as exc:  # noqa: BLE001
        if listener.isCancelled():
            return json.dumps({"ok": False, "cancelled": True})
        return json.dumps({"ok": False, "error": core.clean_error(exc)})
