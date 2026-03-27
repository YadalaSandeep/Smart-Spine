"""
utils.py
Session statistics, score calculation, exercise recommendations,
bone health index, and Firebase Firestore persistence.
"""

import time
import json
import os
from collections import deque
from datetime import datetime


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

STATS_FILE = os.path.join(os.path.dirname(__file__), "stats.json")

EXERCISES = [
    {
        "name": "Neck Stretch",
        "icon": "🧘",
        "description": "Gently tilt your head to the right and hold for 15 seconds, then switch sides.",
        "duration": "30 sec each side",
        "benefit": "Relieves neck tension and forward head posture",
    },
    {
        "name": "Shoulder Roll",
        "icon": "💪",
        "description": "Roll your shoulders backwards in large circles, 10 reps forward then 10 backward.",
        "duration": "1 minute",
        "benefit": "Reduces shoulder hunching and stiffness",
    },
    {
        "name": "Cat-Cow Stretch",
        "icon": "🐱",
        "description": "On hands and knees, arch your back upward (cat) then let it sink (cow). Repeat.",
        "duration": "10 reps",
        "benefit": "Improves spine flexibility and relieves back pain",
    },
    {
        "name": "Chest Opener",
        "icon": "🌟",
        "description": "Clasp hands behind your back, squeeze shoulder blades and lift chest gently.",
        "duration": "20 sec hold × 3",
        "benefit": "Counteracts rounded shoulders from desk work",
    },
    {
        "name": "Back Extension",
        "icon": "🏋️",
        "description": "Lie face down, place hands by shoulders and gently push up, holding for 10 sec.",
        "duration": "5-10 reps",
        "benefit": "Strengthens lower back and improves lumbar posture",
    },
    {
        "name": "Chin Tuck",
        "icon": "👤",
        "description": "Sit tall, draw chin straight back (creating a double chin), hold 5 seconds.",
        "duration": "10 reps",
        "benefit": "Corrects forward head posture and strengthens deep neck muscles",
    },
]


# ---------------------------------------------------------------------------
# Session Statistics
# ---------------------------------------------------------------------------

class SessionStats:
    """Thread-safe session posture statistics tracker."""

    HISTORY_MAX = 300

    def __init__(self):
        self.reset()

    def reset(self):
        self.session_start       = time.time()
        self.good_duration       = 0.0
        self.bad_duration        = 0.0
        self.last_posture        = "Unknown"
        self.last_update_time    = time.time()
        self.consecutive_bad_sec = 0.0
        self.alert_active        = False
        self.bad_streak_count    = 0
        self.score_history       = deque(maxlen=self.HISTORY_MAX)
        self.posture_labels      = deque(maxlen=self.HISTORY_MAX)
        self.angles              = {}
        self.landmarks_detected  = False

    def update(self, posture: str, angles: dict, landmarks_ok: bool):
        now    = time.time()
        delta  = now - self.last_update_time
        self.last_update_time   = now
        self.angles             = angles
        self.landmarks_detected = landmarks_ok

        if posture == "Good Posture":
            self.good_duration       += delta
            self.consecutive_bad_sec  = 0.0
            self.alert_active         = False
        elif posture == "Bad Posture":
            self.bad_duration        += delta
            self.consecutive_bad_sec += delta
            if self.consecutive_bad_sec >= 0.5:
                self.alert_active = True
            if self.last_posture != "Bad Posture":
                self.bad_streak_count += 1
        else:
            self.consecutive_bad_sec = 0.0

        self.last_posture = posture

        score = ScoreCalculator.posture_score(self.good_duration, self.bad_duration)
        self.score_history.append(round(score, 1))
        self.posture_labels.append(posture)

    def to_dict(self) -> dict:
        good    = self.good_duration
        bad     = self.bad_duration
        score   = ScoreCalculator.posture_score(good, bad)
        bhi     = ScoreCalculator.bone_health_index(good, bad, self.bad_streak_count)
        elapsed = time.time() - self.session_start

        return {
            "posture":             self.last_posture,
            "alert_active":        self.alert_active,
            "consecutive_bad_sec": round(self.consecutive_bad_sec, 1),
            "good_duration":       round(good, 1),
            "bad_duration":        round(bad, 1),
            "session_duration":    round(elapsed, 1),
            "posture_score":       round(score, 1),
            "bone_health_index":   round(bhi, 1),
            "bad_streak_count":    self.bad_streak_count,
            "score_history":       list(self.score_history),
            "angles":              self.angles,
            "landmarks_detected":  self.landmarks_detected,
            "timestamp":           datetime.now().strftime("%H:%M:%S"),
            "date":                datetime.now().strftime("%Y-%m-%d"),
        }


# ---------------------------------------------------------------------------
# Score Calculator
# ---------------------------------------------------------------------------

class ScoreCalculator:

    @staticmethod
    def posture_score(good_sec: float, bad_sec: float) -> float:
        total = good_sec + bad_sec
        if total < 0.1:
            return 100.0
        return (good_sec / total) * 100.0

    @staticmethod
    def bone_health_index(good_sec: float, bad_sec: float, bad_streaks: int) -> float:
        posture_quality = ScoreCalculator.posture_score(good_sec, bad_sec)
        streak_penalty  = min(bad_streaks * 2, 30)
        total_min       = (good_sec + bad_sec) / 60.0
        time_penalty    = min(max(0, total_min - 30) * 0.5, 20)
        bhi = (posture_quality * 0.70) - streak_penalty - time_penalty
        return max(0.0, min(100.0, bhi))


# ---------------------------------------------------------------------------
# Exercise Recommender
# ---------------------------------------------------------------------------

class ExerciseRecommender:

    @staticmethod
    def recommend(bad_streak_count: int) -> list:
        if bad_streak_count <= 2:
            return EXERCISES[:2]
        elif bad_streak_count <= 5:
            return EXERCISES[:4]
        return EXERCISES


# ---------------------------------------------------------------------------
# Firebase Persistence
# ---------------------------------------------------------------------------

def save_to_firestore(stats_dict: dict) -> bool:
    """
    Save a session summary to the Firestore `posture_sessions` collection.
    Schema (matches frontend field expectations):
      timestamp, date, time, posture_score, bone_health_index,
      good_posture_time (s), bad_posture_time (s),
      good_duration_min, bad_duration_min, session_duration_min,
      bad_streak_count, created_at (server timestamp)
    Returns True on success, False if Firebase is unavailable.
    """
    try:
        from firebase_config import db, is_available
        if not is_available() or db is None:
            print("[Firebase] ℹ️  Not available — session will be saved locally.")
            return False

        from google.cloud import firestore as _fs
        now   = datetime.now()
        good_s = stats_dict.get("good_duration", 0)
        bad_s  = stats_dict.get("bad_duration",  0)
        dur_s  = stats_dict.get("session_duration", 0)

        doc = {
            # ISO timestamp — top-level field requested by user
            "timestamp":             now.strftime("%Y-%m-%dT%H:%M:%S"),
            "date":                  stats_dict.get("date", now.strftime("%Y-%m-%d")),
            "time":                  stats_dict.get("timestamp", now.strftime("%H:%M:%S")),
            # Core metrics
            "posture_score":         round(stats_dict.get("posture_score",     0), 1),
            "bone_health_index":     round(stats_dict.get("bone_health_index", 0), 1),
            # Time in seconds (per user requirement)
            "good_posture_time":     round(good_s, 1),
            "bad_posture_time":      round(bad_s,  1),
            # Convenience duplicates in minutes for charts
            "good_duration_min":     round(good_s / 60, 2),
            "bad_duration_min":      round(bad_s  / 60, 2),
            "session_duration_min":  round(dur_s  / 60, 2),
            "bad_streak_count":      stats_dict.get("bad_streak_count", 0),
            "created_at":            _fs.SERVER_TIMESTAMP,
        }

        _, ref = db.collection("posture_sessions").add(doc)
        print(
            f"[Firebase] ✅ Session saved → posture_sessions/{ref.id}\n"
            f"           score={doc['posture_score']}% | "
            f"good={doc['good_posture_time']}s | "
            f"bad={doc['bad_posture_time']}s | "
            f"dur={doc['session_duration_min']:.1f}min"
        )
        return True

    except Exception as e:
        print(f"[Firebase] ⚠️  Could not save to Firestore: {e}")
        return False


def fetch_sessions_from_firestore(limit: int = 30) -> list:
    """
    Fetch the most recent sessions from Firestore.
    Returns an empty list if Firebase is unavailable.
    """
    try:
        from firebase_config import db, is_available
        if not is_available() or db is None:
            return []

        from google.cloud.firestore_v1 import Query as _FsQuery
        docs = (
            db.collection("posture_sessions")
            .order_by("created_at", direction=_FsQuery.DESCENDING)
            .limit(limit)
            .stream()
        )
        result = []
        for doc in docs:
            d = doc.to_dict()
            d["doc_id"] = doc.id   # include document ID for reference
            # Convert Firestore Timestamp to readable string
            ts = d.get("created_at")
            if hasattr(ts, "strftime"):
                d["created_at"] = ts.strftime("%Y-%m-%d %H:%M")
            elif hasattr(ts, "seconds"):               # DatetimeWithNanoseconds
                from datetime import timezone
                dt = datetime.fromtimestamp(ts.seconds, tz=timezone.utc)
                d["created_at"] = dt.strftime("%Y-%m-%d %H:%M")
            else:
                d["created_at"] = str(ts or "")
            result.append(d)

        print(f"[Firebase] ✅ Fetched {len(result)} session(s) from Firestore.")
        return list(reversed(result))   # oldest first for charts

    except Exception as e:
        print(f"[Firebase] ⚠️  Could not fetch from Firestore: {e}")
        return []


# ---------------------------------------------------------------------------
# Local JSON fallback (persistent — all sessions, no daily reset)
# ---------------------------------------------------------------------------

def _load_store() -> dict:
    """
    Load the local sessions store from stats.json.
    Returns {'sessions': [...]} always.
    Migrates old daily-keyed format transparently.
    """
    if not os.path.exists(STATS_FILE):
        return {"sessions": []}
    try:
        with open(STATS_FILE, "r") as f:
            data = json.load(f)
        # Migrate old format {"date": "...", "sessions": [...]}
        if "date" in data and isinstance(data.get("sessions"), list):
            print("[Local] ⇒ Migrating old daily-format stats.json to persistent format.")
            migrated = {"sessions": data["sessions"]}
            with open(STATS_FILE, "w") as f:
                json.dump(migrated, f, indent=2)
            return migrated
        if isinstance(data.get("sessions"), list):
            return data
    except (json.JSONDecodeError, KeyError):
        pass
    return {"sessions": []}


def save_session_local(stats_dict: dict):
    """
    Append a session summary to stats.json (same schema as Firestore).
    Sessions are NEVER deleted or rotated — all history is kept.
    """
    store  = _load_store()
    now    = datetime.now()
    good_s = stats_dict.get("good_duration", 0)
    bad_s  = stats_dict.get("bad_duration",  0)
    dur_s  = stats_dict.get("session_duration", 0)

    summary = {
        "timestamp":             now.strftime("%Y-%m-%dT%H:%M:%S"),
        "date":                  stats_dict.get("date", now.strftime("%Y-%m-%d")),
        "time":                  stats_dict.get("timestamp", now.strftime("%H:%M:%S")),
        "posture_score":         round(stats_dict.get("posture_score",     0), 1),
        "bone_health_index":     round(stats_dict.get("bone_health_index", 0), 1),
        "good_posture_time":     round(good_s, 1),
        "bad_posture_time":      round(bad_s,  1),
        "good_duration_min":     round(good_s / 60, 2),
        "bad_duration_min":      round(bad_s  / 60, 2),
        "session_duration_min":  round(dur_s  / 60, 2),
        "bad_streak_count":      stats_dict.get("bad_streak_count", 0),
    }
    store["sessions"].append(summary)
    with open(STATS_FILE, "w") as f:
        json.dump(store, f, indent=2)
    n = len(store["sessions"])
    print(
        f"[Local] ✅ Session saved to stats.json\n"
        f"        score={summary['posture_score']}% | "
        f"good={summary['good_posture_time']}s | "
        f"bad={summary['bad_posture_time']}s | "
        f"dur={summary['session_duration_min']:.1f}min | "
        f"total stored: {n}"
    )


def fetch_sessions_local(limit: int = 30) -> list:
    """Return the most recent `limit` sessions from stats.json."""
    store    = _load_store()
    sessions = store.get("sessions", [])
    result   = sessions[-limit:]     # newest `limit` entries
    print(f"[Local] ℹ️  Loaded {len(result)} session(s) from stats.json "
          f"(total stored: {len(sessions)})")
    return result
