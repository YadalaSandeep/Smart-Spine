# 🦴 Smart Spine 

>Smart Spine is a real-time posture detection system that uses computer vision and machine learning to analyze a user’s sitting posture through a webcam. The system identifies good and bad posture and provides alerts when incorrect posture is detected, helping users maintain better spinal alignment during long computer sessions.

---

## ✨ Features

| Feature | Description |
|---|---|
| 📷 **Live Detection** | MediaPipe tracks 33 body landmarks via your webcam in real time |
| 📐 **Posture Analysis** | Measures neck tilt, spine lean, and shoulder unevenness angles |
| 🔔 **Smart Alerts** | Triggers a banner after 5 consecutive seconds of bad posture |
| 🎯 **Posture Score** | Live % score based on good vs bad posture time | |
| 🏃 **Exercise Guide** | Personalised exercise recommendations based on bad-posture frequency |
| ☁️ **Cloud Sync** | Sessions saved to Firebase Firestore (falls back to local JSON) |
| 📊 **Reports Page** | Session history with Chart.js posture-score trend and good/bad time charts |
| 🎬 **Session Summary** | After stopping detection, a summary screen shows your full session stats |

---

## 🗂️ Project Structure

```
spine-health-monitor/
├── app.py                  # Flask app — routes & camera thread
├── posture_detector.py     # MediaPipe PoseLandmarker logic
├── utils.py                # SessionStats, scoring, Firestore/local persistence
├── firebase_config.py      # Firebase Admin SDK initialisation
├── pose_landmarker.task    # MediaPipe model file
├── serviceAccountKey.json  # 🔒 Firebase credentials (NOT committed)
├── stats.json              # Local session fallback (NOT committed)
├── requirements.txt
├── static/
│   ├── style.css           # Unified dark design system
│   ├── detection.js        # Live detection page logic
│   └── reports.js          # Reports page charts & table
└── templates/
    ├── home.html           # Landing page
    ├── detection.html      # Live posture detection page
    └── reports.html        # Posture analytics & history
```

---

## 🚀 Setup

### 1. Clone & install dependencies

```bash
git clone <your-repo-url>
cd spine-health-monitor
pip install -r requirements.txt
```

### 2. Download the MediaPipe model

```bash
python -c "
import urllib.request
urllib.request.urlretrieve(
  'https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/latest/pose_landmarker_lite.task',
  'pose_landmarker.task'
)
print('Model downloaded.')
"
```

### 3. Set up Firebase (optional but recommended)

1. Go to [Firebase Console](https://console.firebase.google.com/) → Create a project
2. Enable **Firestore Database** (start in test mode)
3. Go to **Project Settings → Service Accounts → Generate new private key**
4. Save the downloaded file as `serviceAccountKey.json` in the project root

> Without Firebase, session data is saved locally to `stats.json` only.

### 4. Run the app

```bash
python app.py
```

Open **http://127.0.0.1:5000** in your browser.

---

## 📡 API Reference

| Endpoint | Method | Description |
|---|---|---|
| `/api/stats` | GET | Current session stats JSON |
| `/api/reset` | POST | Save session and reset stats |
| `/api/exercises` | GET | Exercise recommendations |
| `/api/reports` | GET | Session history (Firestore or local) |
| `/api/camera/start` | POST | Start the webcam / detection thread |
| `/api/camera/stop` | POST | Stop the webcam / detection thread |
| `/video_feed` | GET | MJPEG webcam stream |

---

## 🔒 Security Notes

- **Never commit `serviceAccountKey.json`** — it is listed in `.gitignore`
- **`stats.json`** is also excluded from version control

---

## 🛠️ Tech Stack

- **Backend**: Python 3.9+, Flask 2.3+
-  CV**: MediaPipe 0.10+ (`PoseLandmarker`), OpenCV
- **Database**: Firebase Firestore (cloud), JSON file (local fallback)
- **Frontend**: Vanilla HTML/CSS/JS, Chart.js 4, Inter font

---

## 📸 Pages

| Page | Route | Description |
|---|---|---|
| Home | `/` | Landing page with feature overview |
| Live Detection | `/detection` | Webcam feed + real-time posture stats |
| Reports | `/reports` | Session analytics with charts |
