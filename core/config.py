"""
core/config.py
─────────────────────────────────────────────────────────────────────────────
TruthLens AI — Configuration manager.
"""

from __future__ import annotations
import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class AppConfig:
    llm_provider: str = os.getenv("LLM_PROVIDER", "openrouter").lower()
    whisper_model: str = os.getenv("WHISPER_MODEL", "base")
    sample_rate: int = 16000
    video_fps_target: int = 30
    min_speech_duration_sec: float = 3.0
    min_transcript_words: int = 6


config = AppConfig()
