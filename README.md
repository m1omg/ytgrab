# ytgrab

A small cross-platform app for downloading YouTube video and audio, built on
[yt-dlp](https://github.com/yt-dlp/yt-dlp) and ffmpeg.

Runs on Linux, Windows, macOS and Android (7.0 and newer). ffmpeg and QuickJS
(the JavaScript runtime yt-dlp needs for YouTube) are bundled, so there is
nothing else to install.

*Toto si prečítajte po [slovensky](README.sk.md).*

## Download

Grab a build from the [Releases](../../releases) page:

| Platform | File |
| --- | --- |
| Linux | `ytgrab-linux-x86_64` |
| Windows | `ytgrab-windows-x86_64.exe` |
| macOS (Apple Silicon) | `ytgrab-macos-arm64.zip` |
| macOS (Intel) | `ytgrab-macos-x86_64.zip` |
| Android (most phones) | `ytgrab-android-arm64.apk` |
| Android (older 32-bit phones) | `ytgrab-android-arm32.apk` |
| Android (not sure, Chromebooks) | `ytgrab-android-universal.apk` |

On Linux, mark it executable first: `chmod +x ytgrab-linux-x86_64`. It needs
glibc 2.39 or newer: Ubuntu 24.04, Debian 13, LMDE 7, Fedora 40, Linux Mint 22
or later, or a rolling distro such as Arch, CachyOS or openSUSE Tumbleweed
(`ldd --version` shows yours).

On Android, open the downloaded APK and allow your browser or file manager to
install apps when asked. Newer versions install straight over older ones.
Every Android 7.0+ phone runs the universal APK; the arm64 one is the same app
at less than half the size.

The macOS and Windows builds are **unsigned**, because signing certificates
cost money. The OS will warn you on first launch: on macOS right-click the app
and choose *Open*, on Windows click *More info* then *Run anyway*.

## Updates

The app looks for a newer release a few seconds after it opens. When there is
one it says what's new and offers *Update and restart*: it downloads the new
version, checks it against the release's SHA-256, puts it in place of the old
one and starts again, with your settings as they were. *Not now* asks again
next time. While downloads are running it waits until they finish.

*Options → Check for updates now* looks straight away, and *Check for updates
automatically* turns the check at start off. Where the app can't replace
itself, such as a folder it can't write to or a Mac app run straight from the
download, it offers the release page instead.

On Android a card at the top offers the update; the APK for your phone is
downloaded and checked the same way, and Android asks before installing it
(the first time it also asks you to let ytgrab install apps).

## Remembered settings

What you download (video, audio, MP3 or transcript), the resolution, the
container, the audio stream, the MP3 bitrate, the transcript format and the
cover art option are remembered for next time - in the desktop app, on Android
and in the browser version - and so is the desktop app's download folder. A resolution works as a ceiling:
with 1080p chosen, a video that only goes to 720p downloads at 720p, and the
next one at 1080p again.

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
captions is fetched, so it finishes in a second or two. The list offers:

* subtitles *written by people*, when the video has any;
* the *original* - YouTube's automatic captions in the language spoken;
* YouTube's *automatic translations*: Slovak and English first, then every
  other language YouTube translates into.

The app picks its own language if it can, then English, and prefers the
original to a translation - so an English video gets the original English
captions (`en-orig`), while in Slovak the Slovak translation is selected, with
the original one line above it. For several videos at once there's also *Each
video's own language*.

* *Plain text* flattens the captions into one flowing transcript. Timings are
  dropped, and the repeated lines that scrolling auto-captions produce are
  collapsed. This format needs no ffmpeg.
* *SRT* and *WebVTT* keep the timings, for use as real subtitle files.

## Only a part

Tick **Only a part** (on Android, the *Only a part* switch) and type where the
part starts and ends as minutes:seconds - say **From** `16:15` **To** `16:45`.
Long videos take hours:minutes:seconds (`1:02:03`), and a dot or comma works in
place of the colon (`16.15`), which suits a phone's number pad. Leave *From*
empty to start at the beginning, or *To* empty to run to the end.

Only that part is downloaded, not the whole video, and the file name says which
part it is: `… (16m15s-16m45s).mp3`. Audio and MP4 video start exactly where you
asked. MKV can only start video on a keyframe, so an MKV part may begin a moment
(usually a second or two) early.

If ffmpeg can't fetch the part by itself - some servers refuse it - ytgrab
downloads the whole video and cuts the part out, so it still works, just slower.

## Several at once

Downloads go into a list and run **one at a time**, in order - YouTube is
quicker to ask whether you're a bot when several run together. While one is
running, the button reads **Add to queue**: pick the next video and its
settings, and it waits its turn with whatever settings you chose for it.

* **Several links:** paste a list of links (one per line, or with spaces
  between them) into the link box, or share several at once on Android. The
  box shows how many there are, and **Download N links** queues them all with
  the settings below it.
* **Playlists:** fetch a link to a video that sits in a playlist and choose
  *Just this video* or *Whole playlist*. A link to a playlist alone (or a
  channel's videos) downloads all of it. A playlist link among several links
  brings all its videos too.
* Each download in the list has its own progress and buttons: **Cancel** the
  one running, **Remove** one that waits, **Try again** after a failure,
  **Show in folder** (on Android *Open* and *Share*) once it's saved.
  **Cancel all** stops everything; **Clear finished** tidies the list.

Resolution works as a ceiling when several videos share it: *1080p* takes each
video's best up to 1080p. *Only a part* is for one video at a time, so it's off
for several links and whole playlists.

## "Confirm you're not a bot"

YouTube sometimes stops a connection it doesn't trust and asks it to sign in.
There is no captcha to solve: ytgrab answers by quietly retrying through other
YouTube clients, which usually get through, and only shows an error when those
are stopped too.

If that keeps happening on a computer, sign in to YouTube in your browser and
pick that browser under **Options → Use YouTube login from browser**. ytgrab then reads
your YouTube cookies from it on this computer and sends them only to YouTube.
YouTube can temporarily restrict an account that downloads a lot, so a secondary
account is the safer choice. On Windows, Chrome-family browsers usually can't be
read; Firefox can.

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
ffmpeg and the JavaScript runtime are present and runnable — useful if a build
misbehaves.

## Android

The Android app does what the desktop one does - the same modes, options and
download engine - with a phone-shaped screen:

* **Share** a video from the YouTube app (or a browser) and pick ytgrab; the
  link is filled in and read straight away.
* Downloads keep running in the background, one after another, with progress,
  how many are waiting and *Cancel* / *Cancel all* in the notification.
* Finished files land in **Download/ytgrab**, ready for any player, file
  manager or the *Share* button.
* It follows the phone's language (English or Slovak), and on Android 13+ the
  language can be set for ytgrab alone in system settings.

Reading the first video after the app starts takes a few seconds longer than
on a computer: the phone solves YouTube's JavaScript challenge itself, and
older phones are slower at it.

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

A local build bundles QuickJS if it can find one: either a `qjs` on your PATH,
or the pinned release fetched with
`python packaging/fetch_qjs.py linux-x86_64 qjsbin` and passed as
`YTGRAB_QJS=qjsbin/qjs` (targets: `linux-x86_64`, `windows-x86_64`,
`darwin-arm64`, `darwin-x86_64`). Without it, YouTube downloads depend on a
deno or node installed on the machine.

Binaries cannot be cross-compiled: a Windows `.exe` has to be built on Windows
and a macOS `.app` on macOS. The GitHub Actions workflow does all the builds on
GitHub's runners. Merging a new version number in `ytgrab/__init__.py` into
`main` releases it by itself; pushing a tag like `v1.0.0`, or starting the
workflow from the Actions tab, works too.

### Android

`android/` is a Gradle project (Kotlin, Jetpack Compose) that runs the same
`ytgrab/core.py` through [Chaquopy](https://chaquo.com/chaquopy/). It needs
Android's ffmpeg and QuickJS for each phone architecture, built with the NDK:

```bash
export ANDROID_NDK_HOME=/path/to/ndk   # r29
for abi in arm64-v8a armeabi-v7a x86 x86_64; do
  packaging/android/build_natives.sh "$abi" "android/natives/$abi"
done
cd android && ./gradlew assembleRelease
```

Release builds are signed with the key in two repository secrets, so every
version installs over the last: `ANDROID_KEYSTORE_BASE64` (the keystore,
base64-encoded) and `ANDROID_KEYSTORE_PASSWORD`. Without them the Android leg
of the workflow fails and the release goes out with the desktop builds only.
Keep a copy of the keystore: a phone only accepts updates signed with it.

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
