"""
processors/ingestion/video_demuxer.py
─────────────────────────────────────────────────────────────────────────────
TruthLens AI — Video demuxer and audio track separation.
"""

from __future__ import annotations
import os
import subprocess
from typing import Optional, Tuple
from services.media_utils import extract_audio_from_video


def demux_video_to_audio(video_path: str, output_wav_path: str) -> Tuple[bool, Optional[str]]:
    """
    Extract the audio channel from a video file into a 16kHz mono WAV file.
    
    Parameters
    ----------
    video_path : str
        Path to source video file (MP4, WebM, MOV, etc.).
    output_wav_path : str
        Target WAV destination.

    Returns
    -------
    Tuple[bool, Optional[str]]
        (Success boolean, Error message if failed or None)
    """
    if not os.path.exists(video_path):
        return False, f"Video file not found: {video_path}"

    try:
        os.makedirs(os.path.dirname(output_wav_path), exist_ok=True)
        success = extract_audio_from_video(video_path, output_wav_path)
        if success and os.path.exists(output_wav_path) and os.path.getsize(output_wav_path) > 0:
            return True, None
        return False, "Audio extraction resulted in empty file."
    except Exception as exc:
        return False, str(exc)
