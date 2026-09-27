"""
core/constants.py
─────────────────────────────────────────────────────────────────────────────
TruthLens AI — Core constants, identifiers, and configuration defaults.
"""

from __future__ import annotations
import os

# Storage paths
AUDIO_DIR = "audio"
VIDEO_DIR = "video"
ASSETS_DIR = "assets"

os.makedirs(AUDIO_DIR, exist_ok=True)
os.makedirs(VIDEO_DIR, exist_ok=True)

# Performance Category Keys
CAT_SPEAKING_STYLE = "speaking_style"
CAT_BODY_LANGUAGE = "body_language"
CAT_ENGAGEMENT = "engagement"
CAT_CONFIDENCE = "confidence_indicators"
CAT_STORY_QUALITY = "story_quality"

ALL_CATEGORIES = [
    CAT_SPEAKING_STYLE,
    CAT_BODY_LANGUAGE,
    CAT_ENGAGEMENT,
    CAT_CONFIDENCE,
    CAT_STORY_QUALITY
]

# Insufficient data sentinel
INSUFFICIENT_DATA = "Insufficient Data"

# Context profile identifiers
CONTEXT_JOB_INTERVIEW = "job_interview"
CONTEXT_VC_PITCH = "vc_pitch"
CONTEXT_CASUAL_MEETING = "casual_meeting"

DEFAULT_CONTEXT = CONTEXT_JOB_INTERVIEW

CONTEXT_DISPLAY_NAMES = {
    CONTEXT_JOB_INTERVIEW: "💼 Job Interview",
    CONTEXT_VC_PITCH: "🚀 VC Pitch Presentation",
    CONTEXT_CASUAL_MEETING: "☕ Casual Team Meeting"
}

# Primary Feature Navigation Identifiers
FEATURE_LIVE_CAMERA = "🎥 Live Camera Recording"
FEATURE_INDIVIDUAL_VIDEO = "📁 Individual Video Analysis"
FEATURE_COMPARE_ASSESS = "⚖️ Compare & Assess"

ALL_FEATURES = [
    FEATURE_LIVE_CAMERA,
    FEATURE_INDIVIDUAL_VIDEO,
    FEATURE_COMPARE_ASSESS,
]
DEFAULT_FEATURE = FEATURE_LIVE_CAMERA

# Forbidden Deception/Lie-Detection terms
FORBIDDEN_DECEPTION_TERMS = [
    "lying", "liar", "deceptive", "deception", "honest", "honesty",
    "truthful", "truthfulness", "truth score", "deception score",
    "credibility score", "polygraph"
]
