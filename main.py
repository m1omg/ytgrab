#!/usr/bin/env python3
"""Entry point for the ytgrab desktop app."""

import sys


def selftest():
    """Print what the app found at runtime. Useful when a build misbehaves."""
    from pathlib import Path
    from ytgrab import core, __version__
    import yt_dlp
    from PySide6 import QtCore

    print(f"ytgrab   {__version__}")
    print(f"python   {sys.version.split()[0]}")
    print(f"yt-dlp   {yt_dlp.version.__version__}")
    print(f"Qt       {QtCore.__version__}")
    print(f"frozen   {getattr(sys, 'frozen', False)}")
    location = core.ffmpeg_location()
    print(f"ffmpeg   {location or 'NOT FOUND'}")
    if not location:
        return 1

    # Actually run it: a bundled binary can be present but not executable.
    import shutil, subprocess
    exe = location if Path(location).is_file() else (shutil.which("ffmpeg", path=location) or "")
    if not exe:
        print("ffmpeg   FAILED: no runnable binary at that location")
        return 1
    try:
        out = subprocess.run([exe, "-hide_banner", "-encoders"],
                             capture_output=True, text=True, timeout=30).stdout
        ver = subprocess.run([exe, "-hide_banner", "-version"],
                             capture_output=True, text=True, timeout=30).stdout
        print(f"ffmpeg   {ver.splitlines()[0] if ver else 'no version output'}")
    except Exception as exc:
        print(f"ffmpeg   FAILED TO RUN: {exc}")
        return 1

    missing = [e for e in ("libmp3lame", "aac", "libopus") if e not in out]
    print(f"encoders {'all present' if not missing else 'MISSING: ' + ', '.join(missing)}")

    # yt-dlp degrades quietly without these, so check them here rather than
    # letting a download fail at the very last step.
    absent = []
    for label, module in (("mutagen", "mutagen"), ("pycryptodomex", "Cryptodome"),
                          ("websockets", "websockets"), ("brotli", "brotli")):
        try:
            __import__(module)
        except ImportError:
            absent.append(label)
    print(f"optional {'all present' if not absent else 'MISSING: ' + ', '.join(absent)}")

    return 1 if (missing or absent) else 0


def main():
    if "--selftest" in sys.argv:
        sys.exit(selftest())
    if "--version" in sys.argv:
        from ytgrab import __version__
        print(__version__)
        sys.exit(0)

    from ytgrab.gui import main as gui_main
    gui_main()


if __name__ == "__main__":
    main()
