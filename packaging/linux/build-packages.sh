#!/usr/bin/env bash
# Build DLPizer's .deb and .rpm from the one-file Linux program:
#
#   packaging/linux/build-packages.sh VERSION BINARY OUTDIR
#
# Both install it to /opt/dlpizer, with `dlpizer` on the PATH, a menu entry
# and icons, and name the system libraries Qt needs so the package manager
# brings them along. Needs dpkg-deb and rpmbuild, and PySide6 for the icons
# (PYTHON names the interpreter that has it).
set -euo pipefail

VERSION="$1"
BINARY="$(realpath "$2")"
OUT="$(realpath "$3")"
cd "$(dirname "$0")/../.."
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
ROOT="$WORK/root"
SUMMARY="Download YouTube video and audio"
DESCRIPTION="Downloads a video, its original audio, an MP3 or its transcript, one
link or a whole queue at a time. Built on yt-dlp and ffmpeg, both included."

install -Dm755 "$BINARY" "$ROOT/opt/dlpizer/DLPizer"
mkdir -p "$ROOT/usr/bin"
ln -s ../../opt/dlpizer/DLPizer "$ROOT/usr/bin/dlpizer"

QT_QPA_PLATFORM=offscreen "${PYTHON:-python3}" packaging/make_icons.py "$WORK/icons" >/dev/null
for dir in "$WORK"/icons/*/; do
  size="$(basename "$dir")"
  install -Dm644 "$dir/apps/dlpizer.png" "$ROOT/usr/share/icons/hicolor/$size/apps/dlpizer.png"
done

install -Dm644 /dev/stdin "$ROOT/usr/share/applications/dlpizer.desktop" <<DESKTOP
[Desktop Entry]
Type=Application
Version=1.0
Name=DLPizer
GenericName=Video Downloader
GenericName[sk]=Sťahovanie videí
Comment=Download video and audio, or convert audio to MP3
Comment[sk]=Stiahnutie videa a zvuku alebo prevod zvuku do MP3
Exec=dlpizer
Icon=dlpizer
Terminal=false
Categories=AudioVideo;Recorder;
Keywords=youtube;download;video;audio;music;mp3;
Keywords[sk]=youtube;stiahnut;stahovanie;video;zvuk;hudba;mp3;
StartupNotify=true
StartupWMClass=DLPizer
DESKTOP

# --- .deb: Debian, Ubuntu, Linux Mint, LMDE ------------------------------
# The marker tells the app it came from a package, so it updates through
# the package manager rather than replacing a file it doesn't own.
echo deb > "$ROOT/opt/dlpizer/packaged"
mkdir -p "$ROOT/DEBIAN"
cat > "$ROOT/DEBIAN/control" <<CONTROL
Package: dlpizer
Version: $VERSION
Architecture: amd64
Maintainer: m1omg <62194279+m1omg@users.noreply.github.com>
Installed-Size: $(du -sk --exclude=DEBIAN "$ROOT" | cut -f1)
Depends: libegl1, libgl1, libxkbcommon-x11-0, libxcb-cursor0, libxcb-icccm4,
 libxcb-image0, libxcb-keysyms1, libxcb-randr0, libxcb-render-util0,
 libxcb-shape0, libxcb-xinerama0
Section: video
Priority: optional
Homepage: https://github.com/m1omg/ytgrab
Description: $SUMMARY
$(printf '%s\n' "$DESCRIPTION" | sed 's/^/ /')
CONTROL
dpkg-deb --build --root-owner-group "$ROOT" "$OUT/DLPizer-linux-x86_64.deb" >/dev/null
rm -rf "$ROOT/DEBIAN"

# --- .rpm: Fedora, openSUSE ----------------------------------------------
# Libraries are named by what they provide, which every RPM distro shares,
# rather than by package names, which differ between them.
echo rpm > "$ROOT/opt/dlpizer/packaged"
cat > "$WORK/dlpizer.spec" <<SPEC
Name: dlpizer
Version: $VERSION
Release: 1
Summary: $SUMMARY
License: Unspecified
URL: https://github.com/m1omg/ytgrab
BuildArch: x86_64
AutoReqProv: no
Requires: libEGL.so.1()(64bit), libGL.so.1()(64bit), libxkbcommon-x11.so.0()(64bit)
Requires: libxcb-cursor.so.0()(64bit), libxcb-icccm.so.4()(64bit), libxcb-image.so.0()(64bit)
Requires: libxcb-keysyms.so.1()(64bit), libxcb-randr.so.0()(64bit), libxcb-render-util.so.0()(64bit)
Requires: libxcb-shape.so.0()(64bit), libxcb-xinerama.so.0()(64bit)
# Stripping would cut off the archive appended to the program, and every
# PyInstaller program shares one build ID, so its /usr/lib/.build-id link
# would clash with any other such package.
%global __os_install_post %{nil}
%global debug_package %{nil}
%global _build_id_links none

%description
$DESCRIPTION

%install
cp -a "$ROOT/." %{buildroot}/

%files
/opt/dlpizer
/usr/bin/dlpizer
/usr/share/applications/dlpizer.desktop
/usr/share/icons/hicolor/*/apps/dlpizer.png
SPEC
rpmbuild -bb --quiet --define "_topdir $WORK/rpmbuild" "$WORK/dlpizer.spec"
cp "$WORK"/rpmbuild/RPMS/x86_64/dlpizer-*.rpm "$OUT/DLPizer-linux-x86_64.rpm"

echo "built $OUT/DLPizer-linux-x86_64.deb and $OUT/DLPizer-linux-x86_64.rpm"
