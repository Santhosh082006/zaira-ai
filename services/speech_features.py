"""
services/speech_features.py
─────────────────────────────────────────────────────────────────────────────
TruthLens AI — Stage 6: Voice/Speech Behavioral Signals

Extracts acoustic and structural speech features from audio recordings and transcripts.
Never classifies truthfulness or deception.
"""

from __future__ import annotations

import os
import re
import warnings
import numpy as np

try:
    import librosa
except ImportError:
    librosa = None

FILLER_WORDS = {"um", "uh", "hmm", "er", "erm"}

def _count_filler_words(transcript: str) -> int:
    """Count occurrence of defined filler words in the transcript."""
    if not transcript:
        return 0
    words = re.findall(r'\b\w+\b', transcript.lower())
    return sum(1 for w in words if w in FILLER_WORDS)

def _word_count(transcript: str) -> int:
    """Count total alphanumeric words in the transcript."""
    if not transcript:
        return 0
    return len(re.findall(r'\b\w+\b', transcript))

def extract_speech_features(audio_path: str, transcript: str) -> dict:
    """
    Extract observable speech features from an audio file and its transcript.
    Returns a dictionary of neutral measurements. Returns None for unavailable metrics.
    """
    result = {
        "duration_seconds": None,
        "word_count": _word_count(transcript),
        "speaking_rate_wpm": None,
        "pause_count": None,
        "total_pause_duration_sec": None,
        "filler_word_count": _count_filler_words(transcript),
        "pitch_mean_hz": None,
        "pitch_variation_hz": None,
        "energy_mean_db": None,
        "reliability_flag": "good"
    }

    if not audio_path or not os.path.exists(audio_path):
        result["reliability_flag"] = "audio_missing"
        return result

    if librosa is None:
        result["reliability_flag"] = "librosa_missing"
        return result

    try:
        # Suppress PySoundFile / audioread warnings for weird web WAV headers
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            y, sr = librosa.load(audio_path, sr=None, mono=True)
            
        if y is None or len(y) == 0:
            result["reliability_flag"] = "audio_empty"
            return result
            
        duration = librosa.get_duration(y=y, sr=sr)
        result["duration_seconds"] = round(duration, 2)
        
        # Speaking Rate (WPM)
        if duration > 0:
            result["speaking_rate_wpm"] = round((result["word_count"] / duration) * 60, 1)
        else:
            result["speaking_rate_wpm"] = 0.0

        # Energy (RMS -> dB)
        rms = librosa.feature.rms(y=y)[0]
        mean_rms = 0.0
        if len(rms) > 0:
            mean_rms = np.mean(rms)
            if mean_rms > 1e-10: # avoid log10(0)
                result["energy_mean_db"] = round(float(20 * np.log10(mean_rms)), 1)
                
        # Pure silence check
        if mean_rms < 1e-10:
            result["pause_count"] = 1
            result["total_pause_duration_sec"] = duration
            result["pitch_mean_hz"] = None
            result["pitch_variation_hz"] = None
            result["reliability_flag"] = "all_silence"
            return result
                
        # Pause Detection
        # top_db=30 sets threshold 30dB below peak energy to define silence
        non_mute_intervals = librosa.effects.split(y, top_db=30)
        
        pause_count = 0
        total_pause = 0.0
        last_end = 0
        
        if len(non_mute_intervals) == 0:
            # Entirely silence
            pause_count = 1
            total_pause = duration
            result["reliability_flag"] = "all_silence"
        else:
            for start, end in non_mute_intervals:
                gap_samples = start - last_end
                gap_sec = gap_samples / sr
                # Only count gaps > 0.3s as a genuine internal pause (ignoring start/end padding)
                if last_end > 0 and gap_sec > 0.3: 
                    pause_count += 1
                    total_pause += gap_sec
                last_end = end
                
        result["pause_count"] = pause_count
        result["total_pause_duration_sec"] = round(total_pause, 2)
        
        # Pitch Tracking (f0)
        # librosa.yin is reliable for speech f0 but needs sufficient length
        if duration >= 0.5:
            # fmin=50, fmax=400 captures typical human voice range
            f0 = librosa.yin(y, fmin=50, fmax=400, sr=sr)
            # YIN returns values outside range or NaNs for unvoiced segments, filter them
            valid_f0 = f0[(f0 >= 50) & (f0 <= 400)]
            
            if len(valid_f0) > 0:
                result["pitch_mean_hz"] = round(float(np.mean(valid_f0)), 1)
                result["pitch_variation_hz"] = round(float(np.std(valid_f0)), 1)
            else:
                if result["reliability_flag"] == "good":
                    result["reliability_flag"] = "pitch_unreliable"
        else:
            if result["reliability_flag"] == "good":
                result["reliability_flag"] = "audio_too_short"

    except Exception:
        result["reliability_flag"] = "processing_error"
        
    return result
