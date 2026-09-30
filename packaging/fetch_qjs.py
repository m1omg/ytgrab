#!/usr/bin/env python3
"""Fetch the QuickJS-ng binary for a specific target platform.

yt-dlp needs a JavaScript runtime to solve the challenges YouTube puts in front
of its streams; without one it is left with a single fallback client, a mode it
calls deprecated. QuickJS-ng is one self-contained binary of a couple of
megabytes, so the app ships it rather than asking users to install deno or
node. The release is pinned and the file is checked against its known hash
before it goes into a build.

Usage: fetch_qjs.py <target> <output-dir>
Targets: linux-x86_64, windows-x86_64, darwin-arm64, darwin-x86_64
Prints the path of the downloaded binary on stdout.
"""

import hashlib
import os
import ssl
import sys
import urllib.request

VERSION = "v0.17.0"
URL = "https://github.com/quickjs-ng/quickjs/releases/download/%s/%s"

# target -> (release asset, sha256)
ASSETS = {
    "linux-x86_64": ("qjs-linux-x86_64",
                     "0bfc02511a9f549c28b53880d988fc7cd5d361e90c5e8afdfcd7dc6774ceace5"),
    "windows-x86_64": ("qjs-windows-x86_64.exe",
                       "2aeabf0092c3262d6b2609824418f7dd7ed1f1df939f73b2b15645230cac0d77"),
    "darwin-arm64": ("qjs-darwin-arm64",
                     "8be3ddfe3397d2e692e4e1e8972ee9d032a0a580505d2f8b4ea528cf1b651c11"),
    "darwin-x86_64": ("qjs-darwin-x86_64",
                      "9e5e101b4fd13cda3204222ca9f8be35412c41dcdef3745829633b7a67245412"),
}


def main():
    if len(sys.argv) != 3 or sys.argv[1] not in ASSETS:
        sys.exit(__doc__)
    target, out_dir = sys.argv[1], sys.argv[2]
    asset, expected = ASSETS[target]

    # Some runner Pythons can't find a CA store of their own, so certifi's is
    # added to whatever the system provides.
    context = ssl.create_default_context()
    try:
        import certifi
        context.load_verify_locations(certifi.where())
    except ImportError:
        pass

    url = URL % (VERSION, asset)
    with urllib.request.urlopen(url, timeout=120, context=context) as response:
        data = response.read()
    actual = hashlib.sha256(data).hexdigest()
    if actual != expected:
        sys.exit("%s: sha256 %s does not match the pinned %s" % (asset, actual, expected))

    os.makedirs(out_dir, exist_ok=True)
    target_path = os.path.join(out_dir, "qjs.exe" if target.startswith("windows") else "qjs")
    with open(target_path, "wb") as fh:
        fh.write(data)
    os.chmod(target_path, 0o755)
    print("fetched %s %s (%d bytes)" % (asset, VERSION, len(data)), file=sys.stderr)
    print(os.path.abspath(target_path))


if __name__ == "__main__":
    main()
