"""
services/speech_to_text.py
─────────────────────────────────────────────────────────────────────────────
TruthLens AI — High-Performance Speech-to-Text Service.

Responsibilities:
  • Load (and cache) a local Speech-to-Text Whisper model.
  • Prioritizes faster-whisper (CTranslate2, 3-4x faster on CPU, INT8 quantization).
  • Falls back gracefully to standard OpenAI Whisper.
  • Accept a path to an audio file (WAV/WebM/MP3) and return transcribed text.
"""

from __future__ import annotations
import os
from typing import Any, Union

DEFAULT_MODEL_SIZE: str = "base"


# ── Model loader ───────────────────────────────────────────────────────────────

def load_whisper_model(model_size: str = DEFAULT_MODEL_SIZE) -> Any:
    """
    Load a speech-to-text model.
    Prioritizes faster-whisper (3-4x faster on CPU with INT8 quantization)
    and falls back to standard openai-whisper if unavailable.
    """
    # 1. Attempt faster-whisper
    try:
        from faster_whisper import WhisperModel
        # int8 compute type provides near-lossless transcription at high CPU throughput
        model = WhisperModel(model_size, device="cpu", compute_type="int8")
        return {"engine": "faster_whisper", "model": model}
    except Exception:
        pass

    # 2. Fall back to standard openai-whisper
    try:
        import whisper
    except OSError as e:
        if "4551" in str(e):
            raise RuntimeError(
                "Windows Application Control (Smart App Control) blocked Whisper's PyTorch dependencies from loading. "
                "Please type your transcript manually, or disable Smart App Control to use local transcription."
            ) from e
        raise e

    model = whisper.load_model(model_size)
    return {"engine": "openai_whisper", "model": model}


# Alias for backward compatibility
get_whisper_model = load_whisper_model


# ── Transcription ──────────────────────────────────────────────────────────────

def transcribe_audio(model_obj: Any, audio_path: str) -> str:
    """
    Transcribe an audio file using either faster-whisper or openai-whisper.
    Accepts either the dictionary wrapper or a direct model instance.
    """
    if not os.path.exists(audio_path):
        raise FileNotFoundError(
            f"Audio file not found: '{audio_path}'. "
            "Please record your response before transcribing."
        )

    # Unwrap if wrapped
    engine = None
    model = model_obj
    if isinstance(model_obj, dict) and "engine" in model_obj:
        engine = model_obj["engine"]
        model = model_obj["model"]
    elif hasattr(model_obj, "transcribe") and "WhisperModel" in type(model_obj).__name__:
        engine = "faster_whisper"
    else:
        engine = "openai_whisper"

    try:
        if engine == "faster_whisper":
            segments, info = model.transcribe(audio_path, beam_size=5)
            transcript_parts = [segment.text for segment in segments]
            return " ".join(transcript_parts).strip()
        else:
            result = model.transcribe(audio_path, fp16=False)
            if isinstance(result, dict):
                return result.get("text", "").strip()
            return str(result).strip()
    except Exception as exc:
        raise RuntimeError(
            f"Speech transcription failed on '{audio_path}': {exc}"
        ) from exc
