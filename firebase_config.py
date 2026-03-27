"""
firebase_config.py
Initialises Firebase Admin SDK and exposes the Firestore client `db`.
Falls back gracefully if serviceAccountKey.json is missing OR if the
Firestore database has not been created yet (404 on first probe).
"""

import os
import logging

db = None          # Firestore client (None if Firebase is unavailable)
_firebase_ok = False

_KEY_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "serviceAccountKey.json")

try:
    import firebase_admin
    from firebase_admin import credentials, firestore

    if os.path.exists(_KEY_PATH):
        cred = credentials.Certificate(_KEY_PATH)
        firebase_admin.initialize_app(cred)
        _client = firestore.client()

        # ── Probe: verify the database actually exists ────────────────────
        # firestore.client() succeeds even if the database hasn't been
        # created in the console. A lightweight collection list probe
        # catches the 404 early so we can fall back to local storage.
        try:
            # list_collections() is a generator; calling next() or list()
            # issues one RPC which will raise if DB doesn't exist.
            list(_client.collections())
            db = _client
            _firebase_ok = True
            print("[Firebase] ✅ Connected to Firestore successfully.")
        except Exception as probe_err:
            print(
                f"[Firebase] ⚠️  Firestore database not ready: {probe_err}\n"
                "  → Go to https://console.firebase.google.com → "
                "Firestore Database → Create database.\n"
                "  Sessions will be saved locally until Firestore is set up."
            )
    else:
        print(
            "[Firebase] ⚠️  serviceAccountKey.json not found at:\n"
            f"  {_KEY_PATH}\n"
            "  Sessions will NOT be saved to Firestore.\n"
            "  Follow the README to set up Firebase."
        )

except ImportError:
    print("[Firebase] firebase-admin not installed. Run: pip install firebase-admin")
except Exception as e:
    print(f"[Firebase] Initialisation failed: {e}")


def is_available() -> bool:
    return _firebase_ok
