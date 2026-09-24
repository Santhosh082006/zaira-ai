"""
services/speech_to_text.py
─────────────────────────────────────────────────────────────────────────────
TruthLens AI — Stage 2: Whisper-based speech-to-text service.

Responsibilities:
  • Load (and cache) a local OpenAI Whisper model.
  • Accept a path to a WAV file and return the transcribed text.

Design notes:
  • Model loading is intentionally separated from transcription so that
    Streamlit's @st.cache_resource decorator can keep the model in memory
    between reruns without reloading it from disk every time.
  • No API keys are used; everything runs locally.
"""

from __future__ import annotations

import os


# ── Constants ──────────────────────────────────────────────────────────────────

# "base" runs well on a student laptop (CPU-only, ~140 MB).
# Change to "small" (~460 MB) for slightly better accuracy if RAM allows.
DEFAULT_MODEL_SIZE: str = "base"


# ── Model loader ───────────────────────────────────────────────────────────────

def load_whisper_model(model_size: str = DEFAULT_MODEL_SIZE) -> whisper.Whisper:
    """
    Load a Whisper model from disk (or download it on first run).

    Parameters
    ----------
    model_size : str
        Whisper model variant. Recommended options for a laptop:
        - "tiny"  (~39 MB)  – fastest, lowest accuracy
        - "base"  (~74 MB)  – good balance of speed and accuracy  ← default
        - "small" (~244 MB) – better accuracy, slower on CPU

    Returns
    -------
    whisper.Whisper
        The loaded Whisper model instance.
    """
    try:
        import whisper
    except OSError as e:
        if "4551" in str(e):
            raise RuntimeError(
                "Windows Application Control (Smart App Control) blocked Whisper's PyTorch dependencies from loading. "
                "Please type your transcript manually, or disable Smart App Control to use local transcription."
            ) from e
        raise e
        
    return whisper.load_model(model_size)


# Alias for backward compatibility
get_whisper_model = load_whisper_model


# ── Transcription ──────────────────────────────────────────────────────────────

def transcribe_audio(model: whisper.Whisper, audio_path: str) -> str:
    """
    Transcribe an audio file using the provided Whisper model.

    Parameters
    ----------
    model : whisper.Whisper
        A loaded Whisper model (returned by load_whisper_model).
    audio_path : str
        Absolute or relative path to the audio file (WAV, MP3, etc.).

    Returns
    -------
    str
        The transcribed text, stripped of leading/trailing whitespace.

    Raises
    ------
    FileNotFoundError
        If the audio file does not exist at the given path.
    RuntimeError
        If Whisper fails to process the audio.
    """
    if not os.path.exists(audio_path):
        raise FileNotFoundError(
            f"Audio file not found: '{audio_path}'. "
            "Please record your story before transcribing."
        )

    try:
        result = model.transcribe(audio_path, fp16=False)
        return result["text"].strip()
    except Exception as exc:
        raise RuntimeError(
            f"Whisper failed to transcribe '{audio_path}': {exc}"
        ) from exc
