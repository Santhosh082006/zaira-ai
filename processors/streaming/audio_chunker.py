"""
processors/streaming/audio_chunker.py
─────────────────────────────────────────────────────────────────────────────
TruthLens AI — Audio stream chunker.
"""

from __future__ import annotations
import os
from typing import Generator, Tuple
import numpy as np


def chunk_audio_samples(
    audio_data: np.ndarray,
    sample_rate: int = 16000,
    chunk_sec: float = 2.0
) -> Generator[Tuple[int, np.ndarray], None, None]:
    """
    Split audio numpy buffer into sequential time chunks.
    """
    chunk_size = int(sample_rate * chunk_sec)
    for i in range(0, len(audio_data), chunk_size):
        chunk = audio_data[i : i + chunk_size]
        yield (i // chunk_size, chunk)
