"""
processors/streaming/frame_grabber.py
─────────────────────────────────────────────────────────────────────────────
TruthLens AI — Video frame grabber helper.
"""

from __future__ import annotations
import os
from typing import Generator, Optional
import cv2


def stream_video_frames(
    video_path: str,
    target_fps: int = 10,
    max_duration_sec: Optional[float] = None
) -> Generator[cv2.Mat, None, None]:
    """
    Yield sampled frames from video at target_fps rate.
    """
    if not os.path.exists(video_path):
        return

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return

    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    skip_interval = max(1, int(round(fps / target_fps)))
    frame_idx = 0
    total_yielded = 0
    max_frames = int(max_duration_sec * target_fps) if max_duration_sec else None

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            if frame_idx % skip_interval == 0:
                yield frame
                total_yielded += 1
                if max_frames and total_yielded >= max_frames:
                    break
            frame_idx += 1
    finally:
        cap.release()
