"""The download queue shared by the desktop app and the browser version.

Jobs run one at a time, in the order they were added: YouTube is quicker to
ask whether you're a bot when several downloads run at once. A link that
turns out to be a playlist is replaced by its videos, where it stood.
"""

import threading
import time
import uuid
from pathlib import Path

from . import core, i18n
from .i18n import t

WAITING, RUNNING, DONE, FAILED, CANCELLED = "waiting", "running", "done", "failed", "cancelled"
FINISHED = (DONE, FAILED, CANCELLED)

# Progress reaches listeners at most this often, however fast yt-dlp reports it.
_REPORT_EVERY = 0.25

# yt-dlp reports postprocessor names with the "FFmpeg" prefix stripped.
KNOWN_STAGES = ("ExtractAudio", "Merger", "VideoRemuxer", "VideoConvertor",
                "EmbedThumbnail", "Metadata", "MoveFiles", "SubtitlesConvertor", "Cut")


def stage_key(name):
    """Translation key for a postprocessor, so the label follows the language."""
    return f"stage_{name}" if name in KNOWN_STAGES else "stage_processing"


def summary(job, lang=None):
    """The settings a job downloads with, in a few words."""
    if job.mode == "video":
        best = job.quality in ("best", "", None)
        bits = [t("mode_video", lang),
                t("summary_best", lang) if best else t("summary_up_to", lang, height=job.quality),
                job.container.upper()]
    elif job.mode == "audio":
        bits = [t("mode_audio", lang)] + {"opus": ["Opus"], "m4a": ["AAC"]}.get(job.quality, [])
    elif job.mode == "mp3":
        bits = ["MP3", "V0" if str(job.quality) == "0" else t("summary_kbps", lang, kbps=job.quality)]
    else:
        bits = [t("mode_transcript", lang), job.quality, job.container.upper()]
    if job.section:
        start, end = job.section
        bits.append(f"{core.format_time(start)}–{core.format_time(end) if end is not None else ''}")
    return "  ·  ".join(bits)


def status(job, lang=None):
    """Where a job has got, as (state, numbers) - both may be empty."""
    if job.state == WAITING:
        return t("queue_waiting", lang), ""
    if job.state == DONE:
        name = job.path.name if job.path else ""
        return t("saved", lang), "   ·   ".join(b for b in (name, core.format_size(job.size, lang)) if b)
    if job.state == FAILED:
        return t("failed", lang), ""
    if job.state == CANCELLED:
        return t("cancelled", lang), ""
    if job.cancelling:
        return t("cancelling", lang), ""
    if job.stage:
        return t(job.stage, lang) + "…", ""
    if job.percent >= 0:
        state = t("downloading_percent", lang, percent=i18n.number(job.percent, lang=lang))
    elif job.downloaded:
        state = t("downloading", lang)
    else:
        return t("starting", lang), ""
    bits = []
    if job.total:
        bits.append(f"{core.format_size(job.downloaded, lang)} / {core.format_size(job.total, lang)}")
    if job.speed:
        bits.append(f"{core.format_size(job.speed, lang)}/s")
    if job.eta:
        bits.append(t("eta_left", lang, time=core.format_duration(job.eta)))
    return state, "   ·   ".join(bits)


class Cancelled(Exception):
    """Raised inside a yt-dlp hook to stop the job that is running."""


class Job:
    """One download: what to fetch and how, and how far it has got."""

    def __init__(self, url, dest, mode, quality, container="mp4", embed=True,
                 section=None, title=""):
        self.id = uuid.uuid4().hex
        self.url, self.dest = url, dest
        self.mode, self.quality = mode, quality
        self.container, self.embed = container, embed
        self.section = section
        self.title = title          # known up front for a video that was read
        self.created = time.time()
        self._reset()

    def _reset(self):
        self.state = WAITING
        self.stage = ""             # translation key of the step after the download
        self.percent = -1.0         # negative while the size is unknown
        self.downloaded = self.total = self.speed = self.eta = 0
        self.path = None
        self.size = 0
        self.error = None           # the exception; whoever shows it translates it
        self.login = None           # the browser login it ran with, for that text
        self.cancelling = False
        self.finished = None

    def like(self, url, title=""):
        """A job for another link with the same settings - a playlist's videos."""
        return Job(url, self.dest, self.mode, self.quality, self.container, self.embed,
                   self.section, title)


class DownloadQueue:
    """Runs jobs one after another on a thread of its own.

    on_change(job) is called after a job changes, on whichever thread
    changed it; on_change(None) after jobs are added, removed or replaced.
    login() names the browser to borrow the YouTube login from, or None.
    dest_for(job), if given, is where a job saves instead of job.dest.
    """

    def __init__(self, on_change=None, login=None, dest_for=None):
        self._jobs = []
        self._cond = threading.Condition()
        self._on_change = on_change or (lambda job: None)
        self._login = login or (lambda: None)
        self._dest_for = dest_for
        self._thread = None
        self._closed = False

    # -- reading ----------------------------------------------------------

    def jobs(self):
        with self._cond:
            return list(self._jobs)

    def get(self, job_id):
        with self._cond:
            return next((job for job in self._jobs if job.id == job_id), None)

    def running(self):
        with self._cond:
            return next((job for job in self._jobs if job.state == RUNNING), None)

    def busy(self):
        """Whether anything is downloading or waiting its turn."""
        with self._cond:
            return any(job.state in (WAITING, RUNNING) for job in self._jobs)

    # -- changing ---------------------------------------------------------

    def add(self, jobs):
        with self._cond:
            if self._closed:
                return
            self._jobs.extend(jobs)
            if self._thread is None:
                self._thread = threading.Thread(target=self._run, name="ytgrab-queue", daemon=True)
                self._thread.start()
            self._cond.notify_all()
        self._on_change(None)

    def remove(self, job):
        """Take a job off the list; one that is downloading has to be cancelled first."""
        with self._cond:
            if job.state == RUNNING or job not in self._jobs:
                return
            self._jobs.remove(job)
        self._on_change(None)

    def cancel(self, job):
        """Stop a download, or keep a waiting job from starting."""
        with self._cond:
            if job.state == RUNNING:
                job.cancelling = True   # the next progress report raises Cancelled
            elif job.state == WAITING:
                job.state = CANCELLED
                job.finished = time.time()
            else:
                return
        self._on_change(job)

    def retry(self, job):
        with self._cond:
            if job.state not in (FAILED, CANCELLED) or job not in self._jobs:
                return
            job._reset()
            self._cond.notify_all()
        self._on_change(job)

    def clear_finished(self):
        with self._cond:
            self._jobs = [job for job in self._jobs if job.state not in FINISHED]
        self._on_change(None)

    def cancel_all(self):
        """Stop the download that is running and drop every job waiting its turn."""
        with self._cond:
            self._jobs = [job for job in self._jobs if job.state != WAITING]
            running = next((job for job in self._jobs if job.state == RUNNING), None)
            if running:
                running.cancelling = True
        self._on_change(None)
        if running:
            self._on_change(running)

    def close(self, timeout=3.0):
        """Stop for good: cancel what runs and wait a moment for it to clean up."""
        with self._cond:
            self._closed = True
            for job in self._jobs:
                if job.state == RUNNING:
                    job.cancelling = True
            self._cond.notify_all()
            thread = self._thread
        if thread is not None:
            thread.join(timeout)

    # -- running ----------------------------------------------------------

    def _next(self):
        return next((job for job in self._jobs if job.state == WAITING), None)

    def _run(self):
        while True:
            with self._cond:
                job = self._next()
                while job is None and not self._closed:
                    self._cond.wait()
                    job = self._next()
                if self._closed:
                    return
                job.state = RUNNING
                job.login = self._login()
            self._on_change(job)
            self._download(job)

    def _download(self, job):
        last = [0.0]

        def report(force=False):
            now = time.monotonic()
            if force or now - last[0] >= _REPORT_EVERY:
                last[0] = now
                self._on_change(job)

        def learn_title(d):
            title = (d.get("info_dict") or {}).get("title")
            if title and not job.title:
                job.title = title
                report(force=True)

        def on_progress(d):
            if job.cancelling:
                raise Cancelled()
            learn_title(d)
            if d.get("status") == "downloading":
                total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                done = d.get("downloaded_bytes") or 0
                job.percent = done / total * 100 if total else -1.0
                job.downloaded, job.total = done, total
                job.speed, job.eta = d.get("speed") or 0, d.get("eta") or 0
                job.stage = ""
                report()
            elif d.get("status") == "finished":
                job.stage = "stage_processing"
                report(force=True)

        def on_postprocess(d):
            if job.cancelling:
                raise Cancelled()
            learn_title(d)
            if d.get("status") == "started":
                job.stage = stage_key(d.get("postprocessor") or "")
                report(force=True)

        dest = self._dest_for(job) if self._dest_for else job.dest
        try:
            path = core.download(job.url, dest, job.mode, job.quality, job.container,
                                 job.embed, progress_hook=on_progress,
                                 postprocessor_hook=on_postprocess,
                                 cookies_browser=job.login, section=job.section)
        except core.PlaylistLink as link:
            self._expand(job, link.playlist)
            return
        except Cancelled:
            state, error, path = CANCELLED, None, None
        except Exception as exc:  # noqa: BLE001 - shown on the job's row
            state, error, path = (CANCELLED, None, None) if job.cancelling else (FAILED, exc, None)
        else:
            state, error = DONE, None
            if job.cancelling:  # cancelled as it finished: the file is kept
                job.cancelling = False
        path = Path(path) if path else None
        with self._cond:
            job.state, job.error, job.path = state, error, path
            job.size = path.stat().st_size if path and path.exists() else 0
            job.percent = 100.0 if state == DONE else job.percent
            job.stage = ""
            job.finished = time.time()
            if path and not job.title:
                job.title = path.stem
        self._on_change(job)

    def _expand(self, job, playlist):
        """Put a playlist's videos where its link stood, with the link's settings."""
        # A playlist listing itself would never end.
        entries = [entry for entry in playlist["entries"] if entry["url"] != job.url]
        with self._cond:
            if job not in self._jobs:
                return
            if job.cancelling or not entries:
                job.state = CANCELLED if job.cancelling else FAILED
                job.error = None if job.cancelling else core.DownloadError(
                    "No downloadable video found at that link.")
                job.finished = time.time()
                expanded = False
            else:
                index = self._jobs.index(job)
                self._jobs[index:index + 1] = [job.like(e["url"], e["title"]) for e in entries]
                expanded = True
        self._on_change(None if expanded else job)
