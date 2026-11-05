# app.py — SONORA (with live log stream)
import logging
import queue

from flask import Flask, request, jsonify, render_template, Response, stream_with_context

from backend.directory_service import (
    get_setting, set_setting, validate_directory, run_folder_picker
)
from backend.spotify_service import SpotifyService, SpotifyServiceError
from backend.task_manager import manager
from backend.download_service import start_download_async
from backend.library_service import scan_library
from backend.log_capture import install_log_handler, get_log_queue
from config import FLASK_SECRET_KEY, LOGS_DIR

# --- Logging setup ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(LOGS_DIR / "sonora.log"),
        logging.StreamHandler(),
    ],
)
install_log_handler()             # <-- feeds the terminal panel
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = FLASK_SECRET_KEY


@app.get("/")
def index():
    return render_template("index.html")


# ---------- Settings ----------

@app.get("/api/settings")
def api_get_settings():
    return jsonify({
        "music_dir": get_setting("music_dir"),
        "lyrics_dir": get_setting("lyrics_dir"),
    })


@app.post("/api/settings/select-music-directory")
def api_select_music():
    path = run_folder_picker("Select Music Download Location")
    if not path:
        return jsonify({"ok": False, "message": "No directory selected."}), 400
    ok, msg = validate_directory(path)
    if not ok:
        return jsonify({"ok": False, "message": msg}), 400
    set_setting("music_dir", path)
    return jsonify({"ok": True, "path": path, "message": msg})


@app.post("/api/settings/select-lyrics-directory")
def api_select_lyrics():
    path = run_folder_picker("Select Lyrics Storage Location")
    if not path:
        return jsonify({"ok": False, "message": "No directory selected."}), 400
    ok, msg = validate_directory(path)
    if not ok:
        return jsonify({"ok": False, "message": msg}), 400
    set_setting("lyrics_dir", path)
    return jsonify({"ok": True, "path": path, "message": msg})


# ---------- Analysis ----------

@app.post("/api/analyze")
def api_analyze():
    data = request.get_json(silent=True) or {}
    url = (data.get("url") or "").strip()
    if not url:
        return jsonify({"error": "Missing url"}), 400
    try:
        return jsonify(SpotifyService().analyze(url))
    except SpotifyServiceError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        logger.exception("analyze failed")
        return jsonify({"error": f"Analysis failed: {exc}"}), 500


# ---------- Downloads ----------

@app.post("/api/download")
def api_start_download():
    data = request.get_json(silent=True) or {}
    urls = data.get("urls") or []
    if not urls:
        return jsonify({"error": "No URLs provided."}), 400
    if not get_setting("music_dir"):
        return jsonify({"error": "Select a music directory first."}), 400
    task = manager.create(urls)
    start_download_async(task.id, urls)
    return jsonify({"task_id": task.id})


@app.get("/api/downloads")
def api_list_downloads():
    return jsonify(manager.list())


@app.get("/api/downloads/<tid>")
def api_get_download(tid):
    t = manager.get(tid)
    if not t:
        return jsonify({"error": "Not found"}), 404
    return jsonify(t.to_dict())


@app.post("/api/downloads/<tid>/cancel")
def api_cancel_download(tid):
    t = manager.get(tid)
    if not t:
        return jsonify({"error": "Not found"}), 404
    t.cancel()
    return jsonify({"ok": True})


@app.get("/api/downloads/<tid>/stream")
def api_stream_download(tid):
    task = manager.get(tid)
    if not task:
        return jsonify({"error": "Not found"}), 404

    def generate():
        import json
        while True:
            try:
                evt = task.event_queue.get(timeout=15)
                yield f"data: {json.dumps(evt)}\n\n"
                if evt.get("type") == "finished":
                    break
            except Exception:
                yield ": keep-alive\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ---------- Live logs (terminal panel) ----------

@app.get("/api/logs/stream")
def api_log_stream():
    def generate():
        import json
        q = get_log_queue()
        while True:
            try:
                line = q.get(timeout=15)
                yield f"data: {json.dumps({'line': line})}\n\n"
            except queue.Empty:
                yield ": keep-alive\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ---------- Library ----------

@app.get("/api/library")
def api_library():
    return jsonify(scan_library(get_setting("music_dir") or ""))


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, threaded=True, debug=False)