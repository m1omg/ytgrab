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
    optional = [("mutagen", "mutagen"), ("pycryptodomex", "Cryptodome"),
                ("websockets", "websockets"), ("brotli", "brotli"),
                ("certifi", "certifi")]
    # Reads Chrome-family cookie keys from the keyring, for the browser login.
    if sys.platform.startswith("linux"):
        optional.append(("secretstorage", "secretstorage"))
    for label, module in optional:
        try:
            __import__(module)
        except ImportError:
            absent.append(label)
    # Without its CA bundle certifi imports fine but every HTTPS request fails.
    if "certifi" not in absent:
        import certifi
        if not Path(certifi.where()).is_file():
            absent.append("certifi CA bundle")
    print(f"optional {'all present' if not absent else 'MISSING: ' + ', '.join(absent)}")

    # YouTube only serves working streams to clients that solve its JavaScript
    # challenges, which takes yt-dlp's solver scripts and a runtime to run them.
    js_ok = True
    try:
        import yt_dlp_ejs.yt.solver
        yt_dlp_ejs.yt.solver.core()
        yt_dlp_ejs.yt.solver.lib()
        print(f"solver   yt-dlp-ejs {yt_dlp_ejs.version}")
    except Exception as exc:
        print(f"solver   MISSING ({exc})")
        js_ok = False

    qjs = core.bundled_qjs()
    if qjs:
        try:
            out = subprocess.run([qjs, "-e", "console.log(6 * 7)"],
                                 capture_output=True, text=True, timeout=30).stdout.strip()
        except Exception as exc:
            out = f"failed to run: {exc}"
        print(f"js       {'QuickJS OK' if out == '42' else 'QuickJS FAILED: ' + out} ({qjs})")
        js_ok = js_ok and out == "42"
    else:
        # A packaged build must carry its own; running from source may rely
        # on a deno or node that yt-dlp finds by itself.
        system = [name for name in ("deno", "node", "qjs", "bun") if shutil.which(name)]
        print(f"js       no bundled QuickJS; on PATH: {', '.join(system) or 'nothing'}")
        js_ok = js_ok and bool(system) and not getattr(sys, "frozen", False)

    return 1 if (missing or absent or not js_ok) else 0


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
