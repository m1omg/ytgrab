# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for ytgrab.

Builds a single-file executable for whichever OS it runs on. Bundles a static
ffmpeg so the app works on machines that don't have one installed.
"""

import os
import sys
from PyInstaller.utils.hooks import collect_submodules

block_cipher = None

# yt-dlp loads its extractors lazily, so PyInstaller can't see them statically.
hidden = collect_submodules("yt_dlp")

# Ship a static ffmpeg, named so ytgrab.core finds it under sys._MEIPASS.
# The second tuple element is a destination *directory*, so the binary is first
# copied to a staging dir under the name we want it to keep in the bundle.
binaries = []
try:
    import os
    import shutil as _shutil
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
    print("bundling ffmpeg from %s" % _staged)
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
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="ytgrab",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    runtime_tmpdir=None,
    console=False,          # no terminal window behind the GUI
    disable_windowed_traceback=False,
    argv_emulation=False,   # macOS: don't intercept file-open events
    target_arch=os.environ.get('YTGRAB_TARGET_ARCH') or None,
    codesign_identity=None,
    entitlements_file=None,
)

# macOS additionally gets a proper .app bundle.
if sys.platform == "darwin":
    app = BUNDLE(
        exe,
        name="ytgrab.app",
        icon=None,
        bundle_identifier="dev.ytgrab.app",
        info_plist={
            "NSHighResolutionCapable": True,
            "LSMinimumSystemVersion": "12.0",
            "CFBundleShortVersionString": "1.0.2",
        },
    )
