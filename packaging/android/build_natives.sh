#!/usr/bin/env bash
# Build the helper programs the Android app runs: ffmpeg (with LAME, for MP3,
# and mbedTLS, to fetch just a part of a video itself) and the QuickJS runtime
# yt-dlp needs to solve YouTube's challenges.
#
# Android only lets an app execute files from its native library directory,
# and only files packaged as lib*.so end up there, so the executables are
# named libffmpeg.so and libqjs.so. Both are linked statically: they need no
# libraries beyond the kernel, whatever Android version they land on.
#
# Usage: build_natives.sh <abi> <out-dir>
#   abi: arm64-v8a | armeabi-v7a | x86 | x86_64
# Needs ANDROID_NDK_HOME (or ANDROID_NDK_ROOT), cmake, make and git.
set -euo pipefail

ABI=${1:?abi}
OUT=${2:?out-dir}
API=24   # the app's minSdk

FFMPEG_VERSION=8.1.3
FFMPEG_SHA256=7138d28c96d9d3e3af4ee3d8cad72741f8ffb40da90c1112235dea3ecd3178a3
LAME_VERSION=3.100
LAME_SHA256=ddfe36cab873794038ae2c1210557ad34857a4b6bdc515785d1da9e175b1da1e
MBEDTLS_VERSION=3.6.7
MBEDTLS_SHA256=a7e8bcbec0e6f761b4af24f25677626b35f762f68eef79c08677a363212d11f6
QJS_TAG=v0.17.0
QJS_COMMIT=6d46d07d04041b40f4f49eaa7fdebe44c314c699

NDK=${ANDROID_NDK_HOME:-${ANDROID_NDK_ROOT:-}}
[ -d "$NDK" ] || { echo "Set ANDROID_NDK_HOME to an Android NDK"; exit 1; }
TC=$NDK/toolchains/llvm/prebuilt/linux-x86_64

case "$ABI" in
  arm64-v8a)   TRIPLE=aarch64-linux-android;    FF_ARCH=aarch64; FF_CPU=armv8-a; LAME_HOST=aarch64-linux ;;
  armeabi-v7a) TRIPLE=armv7a-linux-androideabi; FF_ARCH=arm;     FF_CPU=armv7-a; LAME_HOST=arm-linux ;;
  x86)         TRIPLE=i686-linux-android;       FF_ARCH=x86;     FF_CPU=i686;    LAME_HOST=i686-linux ;;
  x86_64)      TRIPLE=x86_64-linux-android;     FF_ARCH=x86_64;  FF_CPU=x86-64;  LAME_HOST=x86_64-linux ;;
  *) echo "unknown ABI: $ABI"; exit 1 ;;
esac

ROOT=$(cd "$(dirname "$0")/../.." && pwd)
SRC=$ROOT/build/android-src
WORK=$ROOT/build/android-natives/$ABI
PREFIX=$WORK/prefix
JOBS=$(nproc 2>/dev/null || echo 4)
mkdir -p "$SRC" "$WORK" "$PREFIX" "$OUT"

CC=$TC/bin/${TRIPLE}${API}-clang
CXX=$TC/bin/${TRIPLE}${API}-clang++
AR=$TC/bin/llvm-ar
NM=$TC/bin/llvm-nm
RANLIB=$TC/bin/llvm-ranlib
STRIP=$TC/bin/llvm-strip

fetch() {  # url sha256 -> path of the verified download
  local url=$1 sum=$2 file=$SRC/$(basename "$1")
  if [ ! -f "$file" ] || ! echo "$sum  $file" | sha256sum -c --quiet - 2>/dev/null; then
    curl -fsSL --retry 3 -o "$file.part" "$url"
    echo "$sum  $file.part" | sha256sum -c --quiet - || { echo "checksum mismatch: $url"; exit 1; }
    mv "$file.part" "$file"
  fi
  echo "$file"
}

# -- LAME (static library only) ---------------------------------------------
if [ ! -f "$PREFIX/lib/libmp3lame.a" ]; then
  tarball=$(fetch "https://downloads.sourceforge.net/project/lame/lame/$LAME_VERSION/lame-$LAME_VERSION.tar.gz" "$LAME_SHA256")
  rm -rf "$WORK/lame" && mkdir -p "$WORK/lame"
  tar -xzf "$tarball" -C "$WORK/lame" --strip-components=1
  (cd "$WORK/lame" &&
    ./configure --host="$LAME_HOST" --prefix="$PREFIX" --disable-shared --enable-static \
      --disable-frontend --disable-decoder \
      CC="$CC" AR="$AR" RANLIB="$RANLIB" CFLAGS="-O2 -fPIC" >/dev/null &&
    make -j"$JOBS" >/dev/null && make install >/dev/null)
fi

# -- mbedTLS (static libraries only) ------------------------------------------
# ffmpeg's HTTPS. It only fetches the part of a video the user asked for;
# everything else is still downloaded by yt-dlp.
if [ ! -f "$PREFIX/lib/libmbedtls.a" ]; then
  tarball=$(fetch "https://github.com/Mbed-TLS/mbedtls/releases/download/mbedtls-$MBEDTLS_VERSION/mbedtls-$MBEDTLS_VERSION.tar.bz2" "$MBEDTLS_SHA256")
  rm -rf "$WORK/mbedtls" && mkdir -p "$WORK/mbedtls"
  tar -xjf "$tarball" -C "$WORK/mbedtls" --strip-components=1
  cmake -S "$WORK/mbedtls" -B "$WORK/mbedtls-build" \
    -DCMAKE_TOOLCHAIN_FILE="$NDK/build/cmake/android.toolchain.cmake" \
    -DANDROID_ABI="$ABI" -DANDROID_PLATFORM="android-$API" \
    -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX="$PREFIX" \
    -DENABLE_PROGRAMS=OFF -DENABLE_TESTING=OFF -DMBEDTLS_FATAL_WARNINGS=OFF \
    -DUSE_SHARED_MBEDTLS_LIBRARY=OFF -DUSE_STATIC_MBEDTLS_LIBRARY=ON >/dev/null
  cmake --build "$WORK/mbedtls-build" -j"$JOBS" >/dev/null
  cmake --install "$WORK/mbedtls-build" >/dev/null
fi

# -- ffmpeg -----------------------------------------------------------------
# Only what yt-dlp asks of it: remuxing and merging streams, MP3 encoding,
# subtitle conversion and cover art - and fetching a part of a stream, which
# is all its network code is for.
asm_flags=()
case "$ABI" in x86|x86_64) asm_flags=(--disable-x86asm) ;; esac  # no nasm needed
ff_config=(
  --target-os=android --arch="$FF_ARCH" --cpu="$FF_CPU" --enable-cross-compile
  --cc="$CC" --cxx="$CXX" --ld="$CC" --ar="$AR" --nm="$NM" --ranlib="$RANLIB" --strip="$STRIP"
  --sysroot="$TC/sysroot" --pkg-config=false
  --extra-cflags="-O2 -I$PREFIX/include" --extra-ldflags="-L$PREFIX/lib"
  --extra-ldexeflags="-static"
  --disable-autodetect --enable-zlib --enable-libmp3lame --enable-mbedtls --enable-version3
  --disable-shared --enable-static --disable-debug --disable-doc
  --disable-ffplay --disable-ffprobe --disable-avdevice
  "${asm_flags[@]}"
)
# A build made with other options (or an older version) is rebuilt, not reused.
stamp="$FFMPEG_VERSION ${ff_config[*]}"
if [ ! -f "$WORK/ffmpeg/ffmpeg" ] || [ "$(cat "$WORK/ffmpeg/.ytgrab-stamp" 2>/dev/null)" != "$stamp" ]; then
  tarball=$(fetch "https://ffmpeg.org/releases/ffmpeg-$FFMPEG_VERSION.tar.xz" "$FFMPEG_SHA256")
  rm -rf "$WORK/ffmpeg" && mkdir -p "$WORK/ffmpeg"
  tar -xJf "$tarball" -C "$WORK/ffmpeg" --strip-components=1
  (cd "$WORK/ffmpeg" && ./configure "${ff_config[@]}" >/dev/null && make -j"$JOBS" >/dev/null)
  printf '%s' "$stamp" > "$WORK/ffmpeg/.ytgrab-stamp"
fi

# -- QuickJS ----------------------------------------------------------------
if [ ! -f "$WORK/qjs-build/qjs" ]; then
  if [ ! -d "$SRC/quickjs/.git" ]; then
    git clone -q --depth 1 --branch "$QJS_TAG" https://github.com/quickjs-ng/quickjs "$SRC/quickjs"
  fi
  actual=$(git -C "$SRC/quickjs" rev-parse HEAD)
  [ "$actual" = "$QJS_COMMIT" ] || { echo "quickjs $QJS_TAG is $actual, expected $QJS_COMMIT"; exit 1; }
  cmake -S "$SRC/quickjs" -B "$WORK/qjs-build" \
    -DCMAKE_TOOLCHAIN_FILE="$NDK/build/cmake/android.toolchain.cmake" \
    -DANDROID_ABI="$ABI" -DANDROID_PLATFORM="android-$API" \
    -DCMAKE_BUILD_TYPE=Release -DQJS_BUILD_CLI_STATIC=ON -DQJS_ENABLE_INSTALL=OFF >/dev/null
  cmake --build "$WORK/qjs-build" --target qjs_exe -j"$JOBS" >/dev/null
fi

# -- collect ----------------------------------------------------------------
"$STRIP" -o "$OUT/libffmpeg.so" "$WORK/ffmpeg/ffmpeg"
"$STRIP" -o "$OUT/libqjs.so" "$WORK/qjs-build/qjs"
for exe in "$OUT/libffmpeg.so" "$OUT/libqjs.so"; do
  # A dynamic dependency would only show up as a crash on the phone.
  if "$TC/bin/llvm-readelf" -d "$exe" | grep -q NEEDED; then
    echo "$exe is not static:"; "$TC/bin/llvm-readelf" -d "$exe" | grep NEEDED; exit 1
  fi
done
ls -l "$OUT"
