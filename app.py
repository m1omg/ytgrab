"""Optional browser version of ytgrab.

Serves the same download engine as the desktop app (ytgrab.core) over a small
local web UI. Bound to 127.0.0.1 - it is not meant to face a network.
"""

import os
import shutil
import threading
import time
from pathlib import Path

from flask import Flask, jsonify, make_response, render_template, request, send_file

from ytgrab import core, i18n, jobs
from ytgrab.i18n import t

BASE_DIR = Path(__file__).resolve().parent
DOWNLOAD_DIR = BASE_DIR / "downloads"
DOWNLOAD_DIR.mkdir(exist_ok=True)

# Finished files are swept after this long.
JOB_TTL_SECONDS = 6 * 3600

app = Flask(__name__)
# One download at a time, each into a directory of its own.
queue = jobs.DownloadQueue(dest_for=lambda job: DOWNLOAD_DIR / job.id)


def pick_language():
    """Language for this request: explicit choice, then cookie, then browser."""
    for candidate in (request.args.get("lang"), request.cookies.get("lang")):
        found = i18n.normalise(candidate)
        if found:
            return found
    for offered, _quality in request.accept_languages:
        found = i18n.normalise(offered)
        if found:
            return found
    return i18n.DEFAULT_LANGUAGE


def job_view(job, lang):
    """What the page shows for a job, in the page's language."""
    state, numbers = jobs.status(job, lang)
    view = {
        "id": job.id,
        "title": job.title or job.url,
        "state": job.state,
        "percent": round(job.percent, 1),
        "busy": job.state == jobs.RUNNING and (job.percent < 0 or bool(job.stage) or job.cancelling),
        "cancelling": job.cancelling,
        "summary": jobs.summary(job, lang),
        "status": state,
        "numbers": numbers,
    }
    if job.state == jobs.DONE and job.path:
        view["filename"] = job.path.name
    if job.state == jobs.FAILED:
        view["error"] = core.clean_error(job.error, lang)
    return view


def discard(job):
    """Take a finished or waiting job off the list, and its file off the disk."""
    queue.remove(job)
    if queue.get(job.id) is None:
        shutil.rmtree(DOWNLOAD_DIR / job.id, ignore_errors=True)


def sweep_old_jobs():
    while True:
        time.sleep(600)
        cutoff = time.time() - JOB_TTL_SECONDS
        for job in queue.jobs():
            if job.state in jobs.FINISHED and (job.finished or job.created) < cutoff:
                discard(job)
        # Also clear directories nothing on the list owns any more.
        listed = {job.id for job in queue.jobs()}
        for path in DOWNLOAD_DIR.iterdir():
            if path.is_dir() and path.name not in listed and path.stat().st_mtime < cutoff:
                shutil.rmtree(path, ignore_errors=True)


@app.route("/")
def index():
    lang = pick_language()
    page = make_response(render_template(
        "index.html", lang=lang, t=i18n.STRINGS[lang],
        languages=[(code, i18n.language_name(code)) for code in i18n.languages()],
        heights=core.STANDARD_HEIGHTS,
    ))
    if request.args.get("lang"):
        page.set_cookie("lang", lang, max_age=365 * 24 * 3600, samesite="Lax")
    return page


@app.post("/api/info")
def api_info():
    lang = pick_language()
    url = (request.json or {}).get("url", "")
    if not core.is_supported_url(url):
        return jsonify(error=t("invalid_link", lang)), 400
    try:
        info = core.fetch_info(url)
    except Exception as exc:  # noqa: BLE001
        return jsonify(error=core.clean_error(exc, lang)), 400
    if not info["transcripts"] and not info["video"]:
        info["transcripts"] = core.common_transcripts(lang)
    return jsonify(info)


def requested_links(data):
    """(url, title) pairs: several links, a playlist's videos, or one link."""
    if isinstance(data.get("items"), list):
        pairs = [(item.get("url"), item.get("title")) for item in data["items"]
                 if isinstance(item, dict)]
    elif isinstance(data.get("urls"), list):
        pairs = [(url, "") for url in data["urls"]]
    else:
        pairs = [(data.get("url"), data.get("title"))]
    return [(url.strip(), str(title or "")[:500]) for url, title in pairs if isinstance(url, str)]


@app.post("/api/download")
def api_download():
    lang = pick_language()
    data = request.json or {}
    mode = data.get("mode", "video")
    container = data.get("container", "mp4")

    links = requested_links(data)
    if not links or not all(core.is_supported_url(url) for url, _title in links):
        return jsonify(error=t("invalid_link", lang)), 400
    if mode not in core.MODES:
        return jsonify(error=t("err_unknown_mode", lang)), 400
    # In transcript mode the container field carries the subtitle format.
    allowed = core.TRANSCRIPT_FORMATS if mode == "transcript" else core.CONTAINERS
    if container not in allowed:
        return jsonify(error=t("err_unknown_container", lang)), 400

    # "Only a part": the From and To exactly as typed, checked here. It is
    # cut from one video, so it isn't offered for several.
    section = None
    part = data.get("part")
    if isinstance(part, dict) and mode != "transcript" and len(links) == 1:
        try:
            duration = int(float(data.get("duration") or 0))
        except (TypeError, ValueError):
            duration = 0
        try:
            section = core.parse_section(str(part.get("start") or ""), str(part.get("end") or ""),
                                         duration, lang)
        except ValueError as exc:
            return jsonify(error=str(exc)), 400

    quality = str(data.get("quality", "best"))
    embed = bool(data.get("embed_thumbnail", True))
    new = [jobs.Job(url, None, mode, quality, container, embed, section, title)
           for url, title in links]
    queue.add(new)
    return jsonify(job_ids=[job.id for job in new])


@app.get("/api/queue")
def api_queue():
    lang = pick_language()
    return jsonify(jobs=[job_view(job, lang) for job in queue.jobs()])


@app.post("/api/job/<job_id>/cancel")
def api_cancel(job_id):
    job = queue.get(job_id)
    if job:
        queue.cancel(job)
    return jsonify(ok=True)


@app.post("/api/job/<job_id>/retry")
def api_retry(job_id):
    job = queue.get(job_id)
    if job:
        shutil.rmtree(DOWNLOAD_DIR / job.id, ignore_errors=True)
        queue.retry(job)
    return jsonify(ok=True)


@app.delete("/api/job/<job_id>")
def api_delete(job_id):
    job = queue.get(job_id)
    if job:
        discard(job)
    return jsonify(ok=True)


@app.post("/api/queue/clear")
def api_clear():
    for job in queue.jobs():
        if job.state in jobs.FINISHED:
            discard(job)
    return jsonify(ok=True)


@app.post("/api/queue/cancel_all")
def api_cancel_all():
    waiting = [job for job in queue.jobs() if job.state == jobs.WAITING]
    queue.cancel_all()
    for job in waiting:
        shutil.rmtree(DOWNLOAD_DIR / job.id, ignore_errors=True)
    return jsonify(ok=True)


@app.get("/api/file/<job_id>")
def api_file(job_id):
    lang = pick_language()
    job = queue.get(job_id)
    if job is None or job.state != jobs.DONE or job.path is None:
        return jsonify(error=t("err_file_not_ready", lang)), 404

    path = Path(job.path)
    # Make sure nothing outside the downloads directory is ever served.
    if not path.is_file() or DOWNLOAD_DIR not in path.parents:
        return jsonify(error=t("err_file_missing", lang)), 404
    return send_file(path, as_attachment=True, download_name=path.name)


if __name__ == "__main__":
    threading.Thread(target=sweep_old_jobs, daemon=True).start()
    port = int(os.environ.get("PORT", "5000"))
    print(f"\n  DLPizer (browser version) running at http://127.0.0.1:{port}\n")
    app.run(host="127.0.0.1", port=port, threaded=True)
