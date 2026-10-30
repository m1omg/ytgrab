#!/usr/bin/env bash
# Install DLPizer for the current user: binary, icons and a menu entry.
# Everything lands under ~/.local, so no root access is needed.
set -e
cd "$(dirname "$0")/.."

BIN_DIR="$HOME/.local/bin"
ICON_ROOT="$HOME/.local/share/icons/hicolor"
APP_DIR="$HOME/.local/share/applications"
BINARY="dist/DLPizer"

# Icon rendering needs PySide6; prefer the project venv, which has it.
if [ -x ".venv/bin/python" ] && .venv/bin/python -c "import PySide6" 2>/dev/null; then
  PY=".venv/bin/python"
elif python3 -c "import PySide6" 2>/dev/null; then
  PY="python3"
else
  PY=""
fi

[ -f "$BINARY" ] || { echo "No build found at $BINARY - run: pyinstaller --noconfirm ytgrab.spec"; exit 1; }

echo "Installing binary..."
mkdir -p "$BIN_DIR"
install -m 755 "$BINARY" "$BIN_DIR/dlpizer"

# The app used to be called ytgrab; an older install would leave a second entry.
rm -f "$BIN_DIR/ytgrab" "$APP_DIR/ytgrab.desktop" "$ICON_ROOT"/*/apps/ytgrab.png

if [ -n "$PY" ]; then
  echo "Rendering icons..."
  QT_QPA_PLATFORM=offscreen "$PY" packaging/make_icons.py build/icons >/dev/null
fi

if [ -d build/icons ]; then
  echo "Installing icons..."
  for size_dir in build/icons/*/; do
    size="$(basename "$size_dir")"
    mkdir -p "$ICON_ROOT/$size/apps"
    install -m 644 "$size_dir/apps/dlpizer.png" "$ICON_ROOT/$size/apps/dlpizer.png"
  done
else
  echo "Skipping icons (PySide6 not available to render them)."
fi

echo "Writing menu entry..."
mkdir -p "$APP_DIR"
cat > "$APP_DIR/dlpizer.desktop" <<DESKTOP
[Desktop Entry]
Type=Application
Version=1.0
Name=DLPizer
GenericName=Video Downloader
GenericName[sk]=Sťahovanie videí
Comment=Download video and audio, or convert audio to MP3
Comment[sk]=Stiahnutie videa a zvuku alebo prevod zvuku do MP3
Exec=$BIN_DIR/dlpizer
Icon=dlpizer
Terminal=false
Categories=AudioVideo;Recorder;
Keywords=youtube;download;video;audio;music;mp3;
Keywords[sk]=youtube;stiahnut;stahovanie;video;zvuk;hudba;mp3;
StartupNotify=true
StartupWMClass=DLPizer
DESKTOP
chmod 644 "$APP_DIR/dlpizer.desktop"

# Refresh the caches so the entry shows up without logging out.
command -v update-desktop-database >/dev/null && update-desktop-database "$APP_DIR" 2>/dev/null || true
command -v gtk-update-icon-cache   >/dev/null && gtk-update-icon-cache -f -t "$ICON_ROOT" 2>/dev/null || true

echo
echo "Installed. Look for 'DLPizer' in your applications menu under Sound & Video."
