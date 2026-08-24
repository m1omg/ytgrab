#!/usr/bin/env python3
"""Fetch the ffmpeg binary for a specific target platform.

pip installs the wheel matching the *host*, which is wrong when a build is
cross-targeted - an Intel macOS app built on an Apple Silicon runner would
otherwise carry an arm64 ffmpeg it cannot execute. This downloads the wheel
for an explicit platform tag and extracts its binary.

Usage: fetch_ffmpeg.py <platform-tag> <output-dir>
Prints the path of the extracted binary on stdout.
"""

import glob
import os
import subprocess
import sys
import zipfile


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    tag, out_dir = sys.argv[1], sys.argv[2]

    wheel_dir = os.path.join(out_dir, "_wheel")
    os.makedirs(wheel_dir, exist_ok=True)
    subprocess.run(
        [sys.executable, "-m", "pip", "download", "--no-deps",
         "--only-binary=:all:", "--platform", tag, "-d", wheel_dir,
         "imageio-ffmpeg"],
        check=True, stdout=sys.stderr,
    )

    wheels = glob.glob(os.path.join(wheel_dir, "*.whl"))
    if not wheels:
        sys.exit("no imageio-ffmpeg wheel downloaded for %s" % tag)

    with zipfile.ZipFile(wheels[0]) as z:
        names = [n for n in z.namelist()
                 if "/binaries/ffmpeg-" in n and not n.endswith(".md")]
        if not names:
            sys.exit("no ffmpeg binary inside %s" % os.path.basename(wheels[0]))
        name = names[0]
        target = os.path.join(out_dir, "ffmpeg.exe" if tag.startswith("win") else "ffmpeg")
        with open(target, "wb") as fh:
            fh.write(z.read(name))

    os.chmod(target, 0o755)
    print("extracted %s from %s" % (name, os.path.basename(wheels[0])), file=sys.stderr)
    print(os.path.abspath(target))


if __name__ == "__main__":
    main()
