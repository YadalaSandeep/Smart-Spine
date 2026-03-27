"""
app.py
Flask application – multi-page SpineAI:
  GET  /            → home page
  GET  /detection   → live detection page
  GET  /reports     → reports page
  GET  /video_feed  → MJPEG stream
  GET  /api/stats   → live session stats JSON
  POST /api/reset   → end session (saves to Firestore/local), reset stats
  GET  /api/exercises → exercise recommendations
  GET  /api/reports   → session history from Firestore (or local JSON)
"""

import cv2
import threading
import time
from flask import Flask, Response, render_template, jsonify, request
from posture_detector import PostureDetector
from utils import (
    SessionStats, ExerciseRecommender,
    save_to_firestore, fetch_sessions_from_firestore,
    save_session_local, fetch_sessions_local,
)

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = Flask(__name__)

# ---------------------------------------------------------------------------
# Shared state
# ---------------------------------------------------------------------------

_lock              = threading.Lock()
_frame_lock        = threading.Lock()   # guards _raw_frame only
_session_stats     = SessionStats()
_detector          = None
_camera_active     = False
_camera_thread_obj = None
_latest_frame      = None
_raw_frame         = None               # latest unprocessed captured frame

# ---------------------------------------------------------------------------
# Camera thread
# ---------------------------------------------------------------------------

def _capture_thread():
    """
    Fast capture loop — grabs frames from the webcam as quickly as possible
    and stores the latest raw frame for the inference thread to consume.
    Does NOT run MediaPipe (so it never blocks on inference).
    """
    global _camera_active, _raw_frame

    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    if not cap.isOpened():
        cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("[WARN] Could not open webcam.")
        _camera_active = False   # signal failure to inference thread
        return

    # 640×480 is plenty — lower res = faster inference & encoding
    cap.set(cv2.CAP_PROP_FRAME_WIDTH,  640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    cap.set(cv2.CAP_PROP_FPS, 30)
    # NOTE: _camera_active is already True (set by _start_camera)
    print("[INFO] Capture thread started (640×480 @ 30 fps).")

    try:
        while _camera_active:
            ret, frame = cap.read()
            if not ret:
                time.sleep(0.01)
                continue
            frame = cv2.flip(frame, 1)
            with _frame_lock:
                _raw_frame = frame          # overwrite with freshest frame
    finally:
        cap.release()
        print("[INFO] Capture thread stopped.")


def _inference_thread():
    """
    Inference loop — pulls the latest raw frame, runs MediaPipe, annotates,
    encodes to JPEG, and updates _latest_frame for the MJPEG stream.
    Runs concurrently with the capture thread so neither blocks the other.
    """
    global _camera_active, _latest_frame, _detector

    _detector = PostureDetector()
    print("[INFO] Inference thread started.")

    try:
        while _camera_active:
            # Grab the freshest raw frame without holding the lock during inference
            with _frame_lock:
                frame = _raw_frame

            if frame is None:
                time.sleep(0.01)
                continue

            annotated, posture, angles, lm_ok = _detector.process_frame(frame)

            with _lock:
                _session_stats.update(posture, angles, lm_ok)

            _, buffer = cv2.imencode(
                ".jpg", annotated,
                [cv2.IMWRITE_JPEG_QUALITY, 75]   # slightly lower → faster encode
            )
            with _lock:
                _latest_frame = buffer.tobytes()

    finally:
        if _detector:
            _detector.release()
        print("[INFO] Inference thread stopped.")


def _start_camera():
    global _camera_active, _camera_thread_obj, _raw_frame
    if _camera_active:
        return  # already running

    # ── Set the flag BEFORE starting threads ────────────────────────────
    # The inference thread loops on `while _camera_active`; if we set it
    # inside _capture_thread (after the camera opens, which takes ~1-3 s on
    # Windows) the inference thread would see False and exit immediately.
    _camera_active = True
    _raw_frame     = None

    tc = threading.Thread(target=_capture_thread,  daemon=True, name="capture")
    ti = threading.Thread(target=_inference_thread, daemon=True, name="inference")
    tc.start()
    ti.start()
    _camera_thread_obj = (tc, ti)
    print("[INFO] Camera threads launched.")


def _stop_camera():
    global _camera_active, _latest_frame
    _camera_active = False   # plain bool write — no lock needed, avoids deadlock
    with _lock:
        _latest_frame = None  # clear stale frame so feed shows blank


# ---------------------------------------------------------------------------
# MJPEG helpers
# ---------------------------------------------------------------------------

def _make_blank_frame() -> bytes:
    import numpy as np
    img = np.zeros((480, 640, 3), dtype=np.uint8)
    cv2.putText(img, "Camera initialising...",
                (80, 240), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (200, 200, 200), 2)
    _, buf = cv2.imencode(".jpg", img)
    return buf.tobytes()


def _gen_frames():
    blank = _make_blank_frame()
    last_sent = None
    while True:
        with _lock:
            frame = _latest_frame
        if frame is None:
            frame = blank
            time.sleep(0.05)
        elif frame is last_sent:
            # No new frame yet — poll fast without re-sending the same bytes
            time.sleep(0.005)
            continue
        last_sent = frame
        yield (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n\r\n" +
            frame + b"\r\n"
        )


# ---------------------------------------------------------------------------
# Page routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return render_template("index.html")

# ---------------------------------------------------------------------------
# API routes
# ---------------------------------------------------------------------------

@app.route("/video_feed")
def video_feed():
    return Response(
        _gen_frames(),
        mimetype="multipart/x-mixed-replace; boundary=frame"
    )


@app.route("/api/camera/start", methods=["POST"])
def api_camera_start():
    """Start the camera thread if not already running."""
    if not _camera_active:
        _start_camera()
    return jsonify({"status": "started", "active": _camera_active})


@app.route("/api/camera/stop", methods=["POST"])
def api_camera_stop():
    """Stop the camera thread and save the current session snapshot."""
    with _lock:
        snapshot = _session_stats.to_dict()

    _stop_camera()

    return jsonify({"status": "stopped", "snapshot": snapshot})


@app.route("/api/stats")
def api_stats():
    with _lock:
        data = _session_stats.to_dict()
    return jsonify(data)


@app.route("/api/save_session", methods=["POST"])
def api_save_session():
    """Receive a session snapshot from the frontend and save to Firestore/Local."""
    data = request.json
    if not data:
        return jsonify({"status": "error", "message": "No data provided"}), 400

    # Ensure keys match what save_to_firestore expects
    # (The frontend might send slightly different names, we normalize here)
    snapshot = {
        "posture_score":     data.get("posture_score", 0),
        "good_duration":     data.get("good_posture_time", 0),
        "bad_duration":      data.get("bad_posture_time", 0),
        "session_duration":  data.get("session_duration", 0),
        "bad_streak_count":  data.get("bad_streak_count", 0),
        "date":              data.get("date"),
        "timestamp":         data.get("time")
    }

    saved = save_to_firestore(snapshot)
    if not saved:
        save_session_local(snapshot)

    return jsonify({"status": "saved", "firebase": saved})


@app.route("/api/reset", methods=["POST"])
def api_reset():
    return jsonify({"status": "reset"})


@app.route("/api/exercises")
def api_exercises():
    with _lock:
        bad_streaks = _session_stats.bad_streak_count
    exercises = ExerciseRecommender.recommend(bad_streaks)
    return jsonify(exercises)


@app.route("/api/sessions")
@app.route("/api/reports")
def api_sessions():
    """
    Return all stored posture sessions.
    Canonical endpoint: /api/sessions
    /api/reports is kept as a backward-compatible alias.

    Response:
      { "sessions": [...], "source": "firestore" | "local", "count": N }
    """
    sessions = fetch_sessions_from_firestore(limit=50)
    source   = "firestore"

    if not sessions:
        sessions = fetch_sessions_local(limit=50)
        source   = "local"

    print(f"[API] /api/sessions → {len(sessions)} session(s) from {source}")
    return jsonify({"sessions": sessions, "source": source, "count": len(sessions)})


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=" * 60)
    print(" AI Powered Smart Spine & Bone Health Monitor")
    print(" Open http://127.0.0.1:5000 in your browser")
    print(" Camera will start when you open Live Detection.")
    print("=" * 60)
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)
