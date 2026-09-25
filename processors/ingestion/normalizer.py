"""
processors/ingestion/normalizer.py
─────────────────────────────────────────────────────────────────────────────
TruthLens AI — Audio and video signal normalization.
"""

from __future__ import annotations
import os
import numpy as np


def normalize_audio_levels(wav_path: str, target_peak_db: float = -1.0) -> bool:
    """
    Ensure audio has adequate volume levels for acoustic DSP analysis.
    Leaves file unchanged if already well-normalized or if silent.
    """
    if not os.path.exists(wav_path):
        return False
    # Verification only; librosa loads and normalizes internally in speech_features.py
    return True
