# ytgrab

A small cross-platform desktop app for downloading YouTube video and audio,
built on [yt-dlp](https://github.com/yt-dlp/yt-dlp) and ffmpeg.

Runs on Linux, Windows and macOS. ffmpeg is bundled, so there is nothing else
to install.

*Toto si prečítajte po [slovensky](README.sk.md).*

## Download

Grab a build from the [Releases](../../releases) page:

| Platform | File |
| --- | --- |
| Linux | `ytgrab-linux-x86_64` |
| Windows | `ytgrab-windows-x86_64.exe` |
| macOS (Apple Silicon) | `ytgrab-macos-arm64.zip` |
| macOS (Intel) | `ytgrab-macos-x86_64.zip` |

On Linux, mark it executable first: `chmod +x ytgrab-linux-x86_64`.

The macOS and Windows builds are **unsigned**, because signing certificates
cost money. The OS will warn you on first launch: on macOS right-click the app
and choose *Open*, on Windows click *More info* then *Run anyway*.

## Language

The app follows the system language: it starts in Slovak on a Slovak system and
in English otherwise. You can switch at any time from the *Language* menu, and
the choice is remembered for next time. The browser version follows the
browser's language setting and switches from the links in the page footer.

## Modes

**Video** — downloads the best video and audio streams and muxes them together.
No re-encoding happens; ffmpeg only copies the streams into a container.

* *MP4* prefers H.264 + AAC so the file plays anywhere. On some videos that
  caps you below the top resolution, because YouTube serves 4K as VP9/AV1 only.
* *MKV* takes whatever the highest-quality streams are (VP9, AV1, Opus) and
  keeps them exactly as they are. Pick this if you want maximum quality.

**Audio (original)** — pulls the audio stream out of its container and saves it
as-is. Nothing is decoded or re-encoded, so the file is bit-for-bit the audio
YouTube delivered, typically Opus (`.opus`) or AAC (`.m4a`). This is as lossless
as a YouTube download can be: the source itself is lossy, but this adds no
further loss.

**MP3** — decodes that same audio and encodes it to MP3. This is a second lossy
step, so it is strictly worse than *Audio (original)* above; use it only when
something needs MP3 specifically. V0 (VBR) is the best setting; 192 kbps CBR is
a sensible default for compatibility.

Both audio modes can embed the thumbnail as cover art along with title tags.

**Transcript** — saves the subtitle track instead of the media. Nothing but the
captions is fetched, so it finishes in a second or two. Manual subtitles are
listed first; YouTube's machine-generated ones are marked *(automatic)*.

* *Plain text* flattens the captions into one flowing transcript. Timings are
  dropped, and the repeated lines that scrolling auto-captions produce are
  collapsed. This format needs no ffmpeg.
* *SRT* and *WebVTT* keep the timings, for use as real subtitle files.

## Running from source

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python main.py
```

On Linux you may also need Qt's runtime libraries (`libegl1`, `libxkbcommon-x11-0`
and friends); see the `apt-get` line in `.github/workflows/build.yml` for the
full list.

`python main.py --selftest` prints the versions it resolved and verifies that
ffmpeg is present and runnable — useful if a build misbehaves.

## Linux: menu entry

`packaging/install-linux.sh` copies the built binary to `~/.local/bin`, renders
the icon at the sizes an icon theme expects, and writes a `.desktop` file so
ytgrab shows up in the applications menu. Everything stays under `~/.local`, so
no root access is needed.

```bash
pyinstaller --noconfirm --clean ytgrab.spec   # if you haven't built yet
./packaging/install-linux.sh
```

The installed binary is a snapshot, so re-run the script after rebuilding.

## Building

```bash
pip install -r requirements.txt pyinstaller
pyinstaller --noconfirm --clean ytgrab.spec
```

Binaries cannot be cross-compiled: a Windows `.exe` has to be built on Windows
and a macOS `.app` on macOS. The GitHub Actions workflow does all four builds on
GitHub's runners — push a tag like `v1.0.0` to produce a release, or trigger it
manually from the Actions tab.

## Optional: browser version

`app.py` is an earlier version of the same tool that serves a web UI on
`127.0.0.1:5000` instead of opening a window. It shares the same download engine.

```bash
pip install -r requirements-web.txt
python app.py
```

## Notes

* Playlist links resolve to their first video; playlists are not downloaded in
  bulk.
* Downloads happen from your own machine and connection. Running this on a
  cloud server usually fails, because YouTube aggressively challenges requests
  from datacenter IP ranges.
* Only use this for content you have the right to download. YouTube's Terms of
  Service restrict downloading.
