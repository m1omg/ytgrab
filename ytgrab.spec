# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for ytgrab.

Linux and Windows build a single self-contained executable. macOS builds a
normal .app directory instead: a onefile app unpacks its entire payload to a
new temp folder on every launch, which macOS then re-scans from scratch
because the path is different each time. That cost minutes on older Macs.

A static ffmpeg is bundled either way, so the app works on machines that
don't have one installed.
"""

import os
import shutil as _shutil
import sys

from PyInstaller.utils.hooks import collect_submodules

block_cipher = None
ONEDIR = sys.platform == "darwin"

# yt-dlp loads its extractors lazily, so PyInstaller can't see them statically.
hidden = collect_submodules("yt_dlp")

# yt-dlp imports these through a helper module, so PyInstaller misses them and
# they silently drop out of the bundle. Without mutagen, embedding cover art in
# m4a/opus/flac fails at the end of a download.
for _optional in ("mutagen", "Cryptodome", "websockets", "brotli"):
    try:
        hidden += collect_submodules(_optional)
    except Exception:
        print("WARNING: optional dependency %s is missing" % _optional)

# Ship a static ffmpeg, named so ytgrab.core finds it beside the app.
# The second tuple element is a destination *directory*, so the binary is first
# copied to a staging dir under the name we want it to keep in the bundle.
binaries = []
staged_ffmpeg = False
try:
    import imageio_ffmpeg

    _wanted = "ffmpeg.exe" if sys.platform == "win32" else "ffmpeg"
    # YTGRAB_FFMPEG lets a cross-targeted build supply the right binary, since
    # imageio_ffmpeg would otherwise hand back the one matching the host.
    _source = os.environ.get("YTGRAB_FFMPEG") or imageio_ffmpeg.get_ffmpeg_exe()
    _stage = os.path.join(os.path.abspath("build"), "ffmpeg-stage")
    os.makedirs(_stage, exist_ok=True)
    _staged = os.path.join(_stage, _wanted)
    _shutil.copy2(_source, _staged)
    os.chmod(_staged, 0o755)
    binaries.append((_staged, "."))
    staged_ffmpeg = True
    print("bundling ffmpeg from %s" % _source)
except Exception as exc:
    print("WARNING: no bundled ffmpeg (%s); the app will need a system one." % exc)

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=binaries,
    datas=[],
    hiddenimports=hidden,
    hookspath=[],
    runtime_hooks=[],
    excludes=[
        "tkinter", "matplotlib", "numpy", "PIL", "flask", "werkzeug",
        "PySide6.QtQml", "PySide6.QtQuick", "PySide6.Qt3DCore",
        "PySide6.QtMultimedia", "PySide6.QtWebEngineCore",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# imageio_ffmpeg carries its own ffmpeg for the host platform. We already stage
# the one we want under a known name, so the spare is dead weight - and on a
# cross-targeted build it is the wrong architecture entirely.
if staged_ffmpeg:
    def _is_spare_ffmpeg(entry):
        dest = str(entry[0]).replace("\\", "/")
        return "imageio_ffmpeg/binaries/" in dest

    dropped = sum(1 for e in a.binaries + a.datas if _is_spare_ffmpeg(e))
    a.binaries = [e for e in a.binaries if not _is_spare_ffmpeg(e)]
    a.datas = [e for e in a.datas if not _is_spare_ffmpeg(e)]
    print("dropped %d redundant imageio_ffmpeg binaries" % dropped)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

common = dict(
    name="ytgrab",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,          # no terminal window behind the GUI
    disable_windowed_traceback=False,
    argv_emulation=False,   # macOS: don't intercept file-open events
    target_arch=os.environ.get("YTGRAB_TARGET_ARCH") or None,
    codesign_identity=None,
    entitlements_file=None,
)

if ONEDIR:
    # Payload lives beside the executable inside the .app, so there is nothing
    # to unpack at startup.
    exe = EXE(pyz, a.scripts, [], exclude_binaries=True, **common)
    coll = COLLECT(
        exe,
        a.binaries,
        a.zipfiles,
        a.datas,
        strip=False,
        upx=False,
        name="ytgrab",
    )
    app = BUNDLE(
        coll,
        name="ytgrab.app",
        icon=None,
        bundle_identifier="dev.ytgrab.app",
        info_plist={
            "NSHighResolutionCapable": True,
            "LSMinimumSystemVersion": "12.0",
            "CFBundleShortVersionString": "1.0.4",
        },
    )
else:
    exe = EXE(
        pyz,
        a.scripts,
        a.binaries,
        a.zipfiles,
        a.datas,
        [],
        runtime_tmpdir=None,
        **common
    )
