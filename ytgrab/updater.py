"""Finding, fetching and installing a newer DLPizer from the GitHub releases.

A packaged build replaces itself. On Windows and Linux the app is one file,
swapped for the new one; on macOS the whole .app is. Windows won't let a
running program be overwritten but does let it be renamed, so the old one
steps aside first and is deleted on the next start. Running from source
there is nothing to swap, so only the release page is offered.
"""

import hashlib
import json
import os
import platform
import re
import shutil
import ssl
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

from . import __version__
from .i18n import t

REPO = "m1omg/ytgrab"
RELEASES_PAGE = f"https://github.com/{REPO}/releases/latest"

_TIMEOUT = 30
_CHUNK = 256 * 1024
# A partial download older than this belongs to no update still running.
_STALE_SECONDS = 24 * 3600


class UpdateError(Exception):
    """An update couldn't be checked for, fetched or put in place."""


class Cancelled(Exception):
    """The person stopped the download."""


@dataclass
class Release:
    version: str                  # "1.5.0"
    page: str                     # the release on GitHub, for a browser
    changes: list = field(default_factory=list)   # what's new, one line each
    url: str = ""                 # this build's file in the release, if any
    size: int = 0
    sha256: str = ""


def _latest_url():
    # YTGRAB_UPDATE_URL points the check somewhere else, to try an update out.
    return (os.environ.get("YTGRAB_UPDATE_URL")
            or f"https://api.github.com/repos/{REPO}/releases/latest")


def parse_version(text):
    """(1, 4, 2) for "v1.4.2" or "1.4.2"; None for anything else."""
    match = re.fullmatch(r"v?(\d+(?:\.\d+){0,3})", (text or "").strip())
    if not match:
        return None
    numbers = tuple(int(n) for n in match.group(1).split("."))
    return numbers + (0,) * (4 - len(numbers))  # so 1.5 and 1.5.0 compare equal


def asset_name():
    """The file in each release that this build is, or None where there's none."""
    machine = platform.machine().lower()
    if sys.platform == "win32":
        return "DLPizer-windows-x86_64.exe" if machine in ("amd64", "x86_64") else None
    if sys.platform == "darwin":
        # The running program's own architecture: the Intel build stays Intel
        # under Rosetta.
        return "DLPizer-macos-%s.zip" % ("arm64" if machine == "arm64" else "x86_64")
    if sys.platform.startswith("linux") and machine in ("x86_64", "amd64"):
        return "DLPizer-linux-x86_64"
    return None


def install_target():
    """What an update replaces: this program's file, or its .app on macOS.

    None when running from source, or from somewhere macOS won't let it be
    replaced (an app opened straight from a download runs from a read-only
    copy).
    """
    if not getattr(sys, "frozen", False):
        return None
    program = Path(sys.executable).resolve()
    if sys.platform != "darwin":
        return program
    app = program.parents[2]
    if app.suffix != ".app" or "/AppTranslocation/" in str(app):
        return None
    return app


def can_replace(target):
    """Whether files can be written beside target - the only real test on Windows."""
    probe = target.parent / f".{target.name}.probe-{os.getpid()}"
    try:
        probe.write_bytes(b"")
        probe.unlink()
        return True
    except OSError:
        return False


def _context():
    # certifi's bundle, as a frozen build's own OpenSSL can't find the
    # system's certificates on many distros.
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:  # noqa: BLE001
        return ssl.create_default_context()


def _open(url, accept, timeout=_TIMEOUT):
    request = urllib.request.Request(url, headers={
        "Accept": accept, "User-Agent": f"DLPizer/{__version__}"})
    try:
        return urllib.request.urlopen(request, timeout=timeout, context=_context())
    except urllib.error.HTTPError as exc:
        raise UpdateError(f"HTTP {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise UpdateError(str(exc.reason)) from exc
    except OSError as exc:
        raise UpdateError(str(exc)) from exc


def _changes(notes):
    """The pull request titles from GitHub's generated notes."""
    found = re.findall(r"^\* (.+?) by @\S+ in https://\S+$", notes or "", re.MULTILINE)
    return [line.strip() for line in found]


def latest():
    """The newest release, described for this build."""
    with _open(_latest_url(), "application/vnd.github+json") as response:
        try:
            data = json.loads(response.read())
            version = parse_version(data["tag_name"])
        except (ValueError, KeyError, TypeError) as exc:
            raise UpdateError(t("update_bad_reply")) from exc
    if not version:
        raise UpdateError(t("update_bad_reply"))
    release = Release(
        version=data["tag_name"].strip().lstrip("v"),
        page=data.get("html_url") or RELEASES_PAGE,
        changes=_changes(data.get("body")),
    )
    wanted = asset_name()
    for asset in data.get("assets") or []:
        if asset.get("name") == wanted:
            release.url = asset.get("browser_download_url") or ""
            release.size = int(asset.get("size") or 0)
            digest = asset.get("digest") or ""
            if digest.startswith("sha256:"):
                release.sha256 = digest.split(":", 1)[1].lower()
    return release


def check(current=__version__):
    """The release to update to, or None when this one is the newest."""
    release = latest()
    if parse_version(release.version) > (parse_version(current) or (0,) * 4):
        return release
    return None


def download(release, dest, progress=None, cancelled=None):
    """Fetch the release's file to dest, and make sure it arrived whole."""
    digest = hashlib.sha256()
    done = 0
    try:
        with _open(release.url, "application/octet-stream") as response, \
                open(dest, "wb") as out:
            total = release.size or int(response.headers.get("Content-Length") or 0)
            while True:
                if cancelled and cancelled():
                    raise Cancelled()
                try:
                    chunk = response.read(_CHUNK)
                except OSError as exc:
                    raise UpdateError(str(exc)) from exc
                if not chunk:
                    break
                out.write(chunk)
                digest.update(chunk)
                done += len(chunk)
                if progress:
                    progress(done, total)
        if release.size and done != release.size:
            raise UpdateError(t("update_incomplete"))
        if release.sha256 and digest.hexdigest() != release.sha256:
            raise UpdateError(t("update_corrupt"))
    except BaseException:
        _remove(dest)
        raise


def install(release, target, progress=None, cancelled=None):
    """Download the release and put it in target's place.

    The download goes beside target, so the swap is a rename on one disk and
    a failure leaves the old version where it was.
    """
    stage = target.parent / f".{target.name}.update"
    _remove(stage)
    try:
        download(release, stage, progress, cancelled)
        if sys.platform == "darwin":
            _install_app(stage, target)
            return
        os.chmod(stage, 0o755)
        if sys.platform == "win32":
            # The running program can't be overwritten, only renamed.
            old = _step_aside(target)
            try:
                os.replace(stage, target)
            except OSError:
                os.replace(old, target)
                raise
        else:
            # The running program keeps the old file open; the name moves on.
            os.replace(stage, target)
    except OSError as exc:
        raise UpdateError(t("update_cant_write", folder=target.parent, reason=exc.strerror or exc)) from exc
    finally:
        _remove(stage)


def _step_aside(target):
    """Rename the running program out of the way; returns its new name."""
    old = target.parent / f".{target.name}.old"
    _remove(old)
    if old.exists():
        # An older version is still running from it.
        old = target.parent / f".{target.name}.old-{os.getpid()}"
    os.replace(target, old)
    return old


def _install_app(archive, app):
    """Unpack the new .app beside the old one and swap them."""
    unpacked = app.parent / f".{app.name}.unpacked"
    _remove(unpacked)
    try:
        # ditto keeps the bundle's symlinks and permissions, which zipfile drops.
        subprocess.run(["ditto", "-x", "-k", str(archive), str(unpacked)],
                       check=True, capture_output=True, timeout=600)
        new = next(unpacked.glob("*.app"), None)
        if new is None:
            raise UpdateError(t("update_corrupt"))
        old = app.parent / f".{app.name}.old"
        _remove(old)
        os.rename(app, old)
        try:
            os.rename(new, app)
        except OSError:
            os.rename(old, app)
            raise
    except subprocess.SubprocessError as exc:
        raise UpdateError(t("update_corrupt")) from exc
    finally:
        _remove(unpacked)


def relaunch(target):
    """Start the installed version as a process of its own."""
    if sys.platform == "darwin":
        subprocess.Popen(["open", "-n", str(target)])
        return
    # Without these the new program would take itself for part of this one
    # and look for its files in this one's temporary folder.
    env = {key: value for key, value in os.environ.items()
           if not key.startswith("_PYI_") and key != "_MEIPASS2"}
    if "LD_LIBRARY_PATH_ORIG" in env:
        env["LD_LIBRARY_PATH"] = env.pop("LD_LIBRARY_PATH_ORIG")
    else:
        env.pop("LD_LIBRARY_PATH", None)
    env["PYINSTALLER_RESET_ENVIRONMENT"] = "1"
    kwargs = {"env": env, "stdin": subprocess.DEVNULL, "stdout": subprocess.DEVNULL,
              "stderr": subprocess.DEVNULL}
    if sys.platform == "win32":
        kwargs["creationflags"] = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True
    subprocess.Popen([str(target)], **kwargs)


def clean_up(target=None, attempts=10, wait=3.0):
    """Delete what an earlier update left beside the program.

    The version it replaced may still be closing; on Windows its file can't
    go until it has, so this tries again for a while.
    """
    target = target or install_target()
    if target is None:
        return
    prefix = f".{target.name}."
    for attempt in range(attempts):
        left = []
        try:
            names = os.listdir(target.parent)
        except OSError:
            return
        for name in names:
            kind = name[len(prefix):].split("-")[0] if name.startswith(prefix) else ""
            path = target.parent / name
            if kind == "old" or (kind in ("update", "unpacked", "probe") and _stale(path)):
                _remove(path)
                if path.exists() or path.is_symlink():
                    left.append(path)
        if not left or attempt == attempts - 1:
            return
        time.sleep(wait)


def _stale(path):
    try:
        return time.time() - path.stat().st_mtime > _STALE_SECONDS
    except OSError:
        return False


def _remove(path):
    path = Path(path)
    try:
        if path.is_dir() and not path.is_symlink():
            shutil.rmtree(path)
        else:
            path.unlink()
    except OSError:
        pass
