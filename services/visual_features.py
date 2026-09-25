"""
services/visual_features.py
─────────────────────────────────────────────────────────────────────────────
TruthLens AI — Stage 7: Webcam / Visual Behavioral Signals

Extracts observable visual markers (blinks, head movement, face presence)
using MediaPipe FaceMesh. Never interprets these signals as deception.
"""

import os
import math
import numpy as np

try:
    import cv2
    import mediapipe as mp
    mp_face_mesh = mp.solutions.face_mesh
except ImportError:
    cv2 = None
    mp = None

# MediaPipe standard landmark indices
# Left eye
LEFT_EYE = [362, 385, 387, 263, 373, 380]
# Right eye
RIGHT_EYE = [33, 160, 158, 133, 153, 144]
# Nose tip
NOSE_TIP = 1

def _dist(p1, p2, width, height):
    """Euclidean distance between two normalized landmarks."""
    return math.hypot((p1.x - p2.x) * width, (p1.y - p2.y) * height)

def _calculate_ear(landmarks, eye_indices, width, height):
    """Calculate Eye Aspect Ratio (EAR) for a single eye."""
    # Vertical distances
    v1 = _dist(landmarks[eye_indices[1]], landmarks[eye_indices[5]], width, height)
    v2 = _dist(landmarks[eye_indices[2]], landmarks[eye_indices[4]], width, height)
    # Horizontal distance
    h = _dist(landmarks[eye_indices[0]], landmarks[eye_indices[3]], width, height)
    
    if h == 0:
        return 0.0
    return (v1 + v2) / (2.0 * h)

def extract_visual_features(video_path: str) -> dict:
    """
    Extract neutral visual behavioral measurements from a video file.
    Returns None for unavailable metrics. Tracks only the primary face.
    """
    result = {
        "face_detected": False,
        "face_presence_ratio": 0.0,
        "head_movement_count": None,
        "head_movement_rate_per_min": None,
        "head_movement_typical_range": "15-35/min",
        "duration_seconds": None,
        "blink_count": None,
        "tracking_reliability": "good"
    }

    if not video_path or not os.path.exists(video_path):
        result["tracking_reliability"] = "video_missing"
        return result

    if cv2 is None or mp is None:
        result["tracking_reliability"] = "dependencies_missing"
        return result

    try:
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            result["tracking_reliability"] = "video_unreadable"
            return result

        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if total_frames <= 0:
            # Some webm files do not report frame count properly, we will count dynamically
            total_frames = 0
            
        frames_processed = 0
        frames_with_face = 0
        
        # State tracking
        blink_count = 0
        is_blinking = False
        EAR_THRESHOLD = 0.22 # Typical threshold for a closed eye
        
        head_movement_count = 0
        last_nose_x = None
        last_nose_y = None
        MOVEMENT_THRESHOLD_RATIO = 0.08 # Scale-invariant displacement relative to face width
        
        # max_num_faces=1 ensures we lock onto the primary/most prominent face
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        step = 2 if fps >= 20 else 1
        frame_idx = 0

        with mp_face_mesh.FaceMesh(
            max_num_faces=1,
            refine_landmarks=True,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5
        ) as face_mesh:
            
            while True:
                success, image = cap.read()
                if not success:
                    break
                    
                frame_idx += 1
                if frame_idx % step != 0:
                    continue

                frames_processed += 1
                height, width, _ = image.shape
                
                # To improve performance, optionally mark image as not writeable
                image.flags.writeable = False
                image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
                results = face_mesh.process(image_rgb)
                
                if results.multi_face_landmarks:
                    frames_with_face += 1
                    result["face_detected"] = True
                    
                    landmarks = results.multi_face_landmarks[0].landmark
                    
                    # 1. Blink Detection
                    left_ear = _calculate_ear(landmarks, LEFT_EYE, width, height)
                    right_ear = _calculate_ear(landmarks, RIGHT_EYE, width, height)
                    avg_ear = (left_ear + right_ear) / 2.0
                    
                    if avg_ear < EAR_THRESHOLD:
                        if not is_blinking:
                            is_blinking = True
                            blink_count += 1
                    else:
                        is_blinking = False
                        
                    # 2. Head Movement (normalized by face width)
                    nose_x = landmarks[NOSE_TIP].x * width
                    nose_y = landmarks[NOSE_TIP].y * height
                    
                    # Approximate face width using lateral face landmarks 234 and 454
                    face_width = max(10.0, math.hypot((landmarks[454].x - landmarks[234].x) * width,
                                                      (landmarks[454].y - landmarks[234].y) * height))
                    
                    if last_nose_x is not None:
                        dist = math.hypot(nose_x - last_nose_x, nose_y - last_nose_y)
                        if (dist / face_width) > MOVEMENT_THRESHOLD_RATIO:
                            head_movement_count += 1
                            last_nose_x = nose_x
                            last_nose_y = nose_y
                    else:
                        last_nose_x = nose_x
                        last_nose_y = nose_y
                else:
                    # Face lost tracking
                    last_nose_x = None
                    last_nose_y = None
                    
        cap.release()
        
        if frames_processed == 0:
            result["tracking_reliability"] = "video_empty"
            return result
            
        result["face_presence_ratio"] = round(frames_with_face / frames_processed, 2)
        
        if result["face_detected"]:
            result["blink_count"] = blink_count
            result["head_movement_count"] = head_movement_count
            if fps and fps > 0 and frame_idx > 0:
                dur_sec = round(frame_idx / fps, 1)
                result["duration_seconds"] = dur_sec
                if dur_sec >= 3.0:
                    result["head_movement_rate_per_min"] = round((head_movement_count / dur_sec) * 60.0, 1)
            if frames_processed < 15:
                result["tracking_reliability"] = "video_too_short"
        else:
            result["tracking_reliability"] = "no_face_found"
            
    except Exception:
        # Fallback for unexpected OpenCV or MediaPipe RuntimeErrors
        result["face_detected"] = None
        result["face_presence_ratio"] = None
        result["head_movement_count"] = None
        result["head_movement_rate_per_min"] = None
        result["duration_seconds"] = None
        result["blink_count"] = None
        result["tracking_reliability"] = "analysis_error"

    return result
