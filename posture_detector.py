"""
posture_detector.py
Pose detection using MediaPipe Tasks API (mediapipe >= 0.10).
Uses PoseLandmarker (LIVE_STREAM mode) for real-time frame processing.
"""

import cv2
import numpy as np
import math
import os
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
from mediapipe.tasks.python.vision import RunningMode


# ── Landmark indices (MediaPipe Pose 33-landmark model) ───────────────────
class LM:
    NOSE           = 0
    LEFT_EAR       = 7
    RIGHT_EAR      = 8
    LEFT_SHOULDER  = 11
    RIGHT_SHOULDER = 12
    LEFT_HIP       = 23
    RIGHT_HIP      = 24
    LEFT_KNEE      = 25
    RIGHT_KNEE     = 26
    LEFT_ANKLE     = 27
    RIGHT_ANKLE    = 28


# ── Connection pairs to draw ───────────────────────────────────────────────
_CONNECTIONS = [
    (LM.LEFT_SHOULDER,  LM.RIGHT_SHOULDER),
    (LM.LEFT_SHOULDER,  LM.LEFT_HIP),
    (LM.RIGHT_SHOULDER, LM.RIGHT_HIP)
]

# ── Posture thresholds ────────────────────────────────────────────────────
NECK_ANGLE_THRESHOLD    = 30    # forward neck tilt (degrees)
SPINE_ANGLE_THRESHOLD   = 20    # back lean (degrees)
SHOULDER_DIFF_THRESHOLD = 15    # shoulder unevenness (% of frame height)

# ── Face / head landmark indices to SKIP when drawing dots ────────────────
# MediaPipe Pose landmarks 0-10 are face/head points (nose, eyes, ears, mouth)
# We only want to draw body landmarks (shoulders, hips, knees, ankles, etc.)
_FACE_LM_INDICES = set(range(11))   # 0..10 inclusive

# ── Model path ────────────────────────────────────────────────────────────
_MODEL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "pose_landmarker.task")


class PostureDetector:
    """Real-time posture detection using MediaPipe Tasks PoseLandmarker."""

    def __init__(self):
        if not os.path.exists(_MODEL_PATH):
            raise FileNotFoundError(
                f"Pose model not found at {_MODEL_PATH}.\n"
                "Run: python -c \"import urllib.request; "
                "urllib.request.urlretrieve('https://storage.googleapis.com/"
                "mediapipe-models/pose_landmarker/pose_landmarker_lite/"
                "float16/latest/pose_landmarker_lite.task', "
                "'pose_landmarker.task')\""
            )

        base_opts = python.BaseOptions(model_asset_path=_MODEL_PATH)
        opts = vision.PoseLandmarkerOptions(
            base_options=base_opts,
            running_mode=RunningMode.IMAGE,
            num_poses=1,
            min_pose_detection_confidence=0.70,   # ↑ was 0.55 — higher accuracy
            min_pose_presence_confidence=0.70,    # ↑ was 0.55
            min_tracking_confidence=0.60,         # ↑ was 0.50
            output_segmentation_masks=False,
        )
        self.landmarker   = vision.PoseLandmarker.create_from_options(opts)
        self.last_posture = "Unknown"
        self.last_angles  = {}

    # ── Geometry ──────────────────────────────────────────────────────────

    @staticmethod
    def _to_px(lm, h, w):
        return np.array([lm.x * w, lm.y * h])

    @staticmethod
    def _vertical_angle(a, b):
        """Angle between vector a→b and the downward vertical [0,1]."""
        vec = b - a
        norm = np.linalg.norm(vec)
        if norm < 1e-6:
            return 0.0
        cos_a = np.dot(vec / norm, np.array([0.0, 1.0]))
        return math.degrees(math.acos(np.clip(cos_a, -1.0, 1.0)))

    # ── Core ──────────────────────────────────────────────────────────────

    def process_frame(self, frame):
        """
        Parameters: BGR frame (numpy array)
        Returns: (annotated_frame, posture_label, angles_dict, landmarks_ok)

        Inference runs on a downscaled copy for speed; landmark coords are
        normalized (0–1) so they project correctly onto the original frame.
        """
        h, w = frame.shape[:2]

        # ── Downscale for inference (faster MediaPipe) ──────────────────
        INFER_W, INFER_H = 480, 270
        if w > INFER_W:
            small = cv2.resize(frame, (INFER_W, INFER_H),
                               interpolation=cv2.INTER_LINEAR)
        else:
            small = frame                   # already small enough
        rgb = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)

        result = self.landmarker.detect(mp_image)

        annotated   = frame.copy()
        posture     = "Unknown"
        angles      = {}
        lm_ok       = False

        if result.pose_landmarks and len(result.pose_landmarks) > 0:
            lm_ok    = True
            landmarks = result.pose_landmarks[0]   # first person

            def pt(idx):
                return self._to_px(landmarks[idx], h, w)

            # Key points
            left_ear       = pt(LM.LEFT_EAR)
            right_ear      = pt(LM.RIGHT_EAR)
            left_shoulder  = pt(LM.LEFT_SHOULDER)
            right_shoulder = pt(LM.RIGHT_SHOULDER)
            left_hip       = pt(LM.LEFT_HIP)
            right_hip      = pt(LM.RIGHT_HIP)

            # Midpoints
            mid_ear      = (left_ear      + right_ear)      / 2
            mid_shoulder = (left_shoulder + right_shoulder) / 2
            mid_hip      = (left_hip      + right_hip)      / 2

            # Angle calculations
            neck_angle          = self._vertical_angle(mid_ear, mid_shoulder)
            spine_angle         = self._vertical_angle(mid_shoulder, mid_hip)
            shoulder_diff_pct   = round(abs(left_shoulder[1] - right_shoulder[1]) / h * 100, 1)
            hip_diff_pct        = round(abs(left_hip[1] - right_hip[1]) / h * 100, 1)

            angles = {
                "neck_tilt":          round(neck_angle, 1),
                "spine_lean":         round(spine_angle, 1),
                "shoulder_diff_pct":  shoulder_diff_pct,
                "hip_diff_pct":       hip_diff_pct,
            }

            # Classify
            issues = []
            if neck_angle > NECK_ANGLE_THRESHOLD:
                issues.append(f"Head fwd ({neck_angle:.0f}°)")
            if spine_angle > SPINE_ANGLE_THRESHOLD:
                issues.append(f"Spine lean ({spine_angle:.0f}°)")
            if shoulder_diff_pct > SHOULDER_DIFF_THRESHOLD:
                issues.append("Uneven shoulders")

            posture           = "Good Posture" if not issues else "Bad Posture"
            self.last_posture = posture
            self.last_angles  = angles

            # ── Draw skeleton connections ──────────────────────────────
            for (a_idx, b_idx) in _CONNECTIONS:
                try:
                    a_pt = pt(a_idx).astype(int)
                    b_pt = pt(b_idx).astype(int)
                    cv2.line(annotated, tuple(a_pt), tuple(b_pt), (100, 100, 255), 2)
                except Exception:
                    pass

            # Remove the custom vertical face alignment lines
            # Spine line (mid_shoulder -> mid_hip)
            # Neck line (mid_ear -> mid_shoulder)

            # ── Info panel (top-left) ──────────────────────────────────
            good   = posture == "Good Posture"
            p_color = (0, 210, 90) if good else (40, 60, 230)
            panel_x, panel_y = 10, 10
            panel_w, panel_h = 260, 130

            # Panel background
            overlay = annotated.copy()
            cv2.rectangle(overlay, (panel_x, panel_y),
                          (panel_x + panel_w, panel_y + panel_h),
                          (15, 18, 30), -1)
            cv2.addWeighted(overlay, 0.75, annotated, 0.25, 0, annotated)

            # Border
            cv2.rectangle(annotated, (panel_x, panel_y),
                          (panel_x + panel_w, panel_y + panel_h),
                          p_color, 2)

            # Status label
            status_txt = "GOOD POSTURE" if good else "BAD POSTURE"
            cv2.putText(annotated, status_txt,
                        (panel_x + 10, panel_y + 28),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, p_color, 2)

            # Divider line
            cv2.line(annotated,
                     (panel_x + 8,  panel_y + 38),
                     (panel_x + panel_w - 8, panel_y + 38),
                     (60, 65, 80), 1)

            # Angle rows
            angle_rows = [
                (f"Neck Tilt  : {neck_angle:.1f} deg",
                 (80, 180, 255) if neck_angle <= NECK_ANGLE_THRESHOLD else (80, 80, 255)),
                (f"Spine Lean : {spine_angle:.1f} deg",
                 (80, 220, 255) if spine_angle <= SPINE_ANGLE_THRESHOLD else (80, 80, 255)),
                (f"Shoulders  : {shoulder_diff_pct:.1f} %",
                 (130, 255, 180) if shoulder_diff_pct <= SHOULDER_DIFF_THRESHOLD else (80, 80, 255)),
            ]
            for i, (txt, col) in enumerate(angle_rows):
                cv2.putText(annotated, txt,
                            (panel_x + 10, panel_y + 60 + i * 24),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.48, col, 1)

            # Issues (top-right corner)
            for i, issue in enumerate(issues):
                cv2.putText(annotated, f"! {issue}",
                            (w - 300, 36 + i * 26),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.55, (60, 90, 255), 2)
        else:
            cv2.rectangle(annotated, (10, 10), (340, 60), (20, 20, 30), -1)
            cv2.putText(annotated, "No Person Detected",
                        (20, 44), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (150, 150, 150), 2)

        return annotated, posture, angles, lm_ok

    def release(self):
        self.landmarker.close()
