"""Optional browser version of ytgrab.

Serves the same download engine as the desktop app (ytgrab.core) over a small
local web UI. Bound to 127.0.0.1 - it is not meant to face a network.
"""

import os
import shutil
import threading
import time
import uuid
from pathlib import Path

from flask import Flask, jsonify, request, send_file, render_template
from yt_dlp.utils import DownloadError

from ytgrab import core

BASE_DIR = Path(__file__).resolve().parent
DOWNLOAD_DIR = BASE_DIR / "downloads"
DOWNLOAD_DIR.mkdir(exist_ok=True)

# Finished files are swept after this long.
JOB_TTL_SECONDS = 6 * 3600

# yt-dlp reports postprocessor names with the "FFmpeg" prefix stripped.
STAGE_LABELS = {
    "ExtractAudio": "extracting audio",
    "Merger": "merging video and audio",
    "VideoRemuxer": "remuxing",
    "VideoConvertor": "converting",
    "EmbedThumbnail": "embedding cover art",
    "Metadata": "writing metadata",
    "MoveFiles": "finishing up",
}

app = Flask(__name__)
jobs = {}
jobs_lock = threading.Lock()


def set_job(job_id, **fields):
    with jobs_lock:
        job = jobs.get(job_id)
        if job is not None:
            job.update(fields)


def make_hooks(job_id):
    def on_progress(d):
        if d.get("status") == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            done = d.get("downloaded_bytes") or 0
            set_job(job_id, state="downloading",
                    percent=round((done / total * 100) if total else 0, 1),
                    downloaded=done, total=total,
                    speed=d.get("speed") or 0, eta=d.get("eta") or 0)
        elif d.get("status") == "finished":
            set_job(job_id, state="processing", percent=100.0, speed=0, eta=0)

    def on_postprocess(d):
        if d.get("status") == "started":
            label = STAGE_LABELS.get(d.get("postprocessor") or "", "processing")
            set_job(job_id, state="processing", stage=label)

    return on_progress, on_postprocess


def run_job(job_id, url, mode, quality, container, embed_thumbnail):
    on_progress, on_postprocess = make_hooks(job_id)
    job_dir = DOWNLOAD_DIR / job_id
    try:
        set_job(job_id, state="starting")
        path = core.download(url, job_dir, mode, quality, container,
                             embed_thumbnail, on_progress, on_postprocess)
        set_job(job_id, state="done", percent=100.0, stage="",
                title=path.stem, filename=path.name, filepath=str(path),
                filesize=path.stat().st_size, finished_at=time.time())
    except (DownloadError, Exception) as exc:  # noqa: BLE001 - surface to the UI
        set_job(job_id, state="error", error=core.clean_error(exc))


def sweep_old_jobs():
    while True:
        time.sleep(600)
        cutoff = time.time() - JOB_TTL_SECONDS
        with jobs_lock:
            stale = [jid for jid, job in jobs.items()
                     if job.get("created_at", 0) < cutoff]
            for jid in stale:
                jobs.pop(jid, None)
        for jid in stale:
            shutil.rmtree(DOWNLOAD_DIR / jid, ignore_errors=True)
        # Also clear directories left behind by a previous run.
        for path in DOWNLOAD_DIR.iterdir():
            if path.is_dir() and path.stat().st_mtime < cutoff:
                shutil.rmtree(path, ignore_errors=True)


@app.route("/")
def index():
    return render_template("index.html")


@app.post("/api/info")
def api_info():
    url = (request.json or {}).get("url", "")
    if not core.is_supported_url(url):
        return jsonify(error="Enter a valid http(s) link."), 400
    try:
        return jsonify(core.fetch_info(url))
    except Exception as exc:  # noqa: BLE001
        return jsonify(error=core.clean_error(exc)), 400


@app.post("/api/download")
def api_download():
    data = request.json or {}
    url = data.get("url", "")
    mode = data.get("mode", "video")
    container = data.get("container", "mp4")

    if not core.is_supported_url(url):
        return jsonify(error="Enter a valid http(s) link."), 400
    if mode not in core.MODES:
        return jsonify(error="Unknown download mode."), 400
    if container not in core.CONTAINERS:
        return jsonify(error="Unknown container."), 400

    job_id = uuid.uuid4().hex
    with jobs_lock:
        jobs[job_id] = {"id": job_id, "state": "queued", "percent": 0.0,
                        "stage": "", "mode": mode, "title": "",
                        "created_at": time.time()}

    threading.Thread(
        target=run_job,
        args=(job_id, url, mode, data.get("quality", "best"), container,
              bool(data.get("embed_thumbnail", True))),
        daemon=True,
    ).start()
    return jsonify(job_id=job_id)


@app.get("/api/status/<job_id>")
def api_status(job_id):
    with jobs_lock:
        job = jobs.get(job_id)
        if job is None:
            return jsonify(error="Unknown job."), 404
        return jsonify({k: v for k, v in job.items() if k != "filepath"})


@app.get("/api/file/<job_id>")
def api_file(job_id):
    with jobs_lock:
        job = jobs.get(job_id)
    if job is None or job.get("state") != "done":
        return jsonify(error="File is not ready."), 404

    path = Path(job["filepath"])
    # Make sure a crafted job id can't escape the downloads directory.
    if not path.is_file() or DOWNLOAD_DIR not in path.parents:
        return jsonify(error="File is missing."), 404
    return send_file(path, as_attachment=True, download_name=path.name)


@app.delete("/api/job/<job_id>")
def api_delete(job_id):
    with jobs_lock:
        jobs.pop(job_id, None)
    shutil.rmtree(DOWNLOAD_DIR / job_id, ignore_errors=True)
    return jsonify(ok=True)


if __name__ == "__main__":
    threading.Thread(target=sweep_old_jobs, daemon=True).start()
    port = int(os.environ.get("PORT", "5000"))
    print(f"\n  ytgrab (browser version) running at http://127.0.0.1:{port}\n")
    app.run(host="127.0.0.1", port=port, threaded=True)
