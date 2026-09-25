"""
processors/context_engine/weighting.py
─────────────────────────────────────────────────────────────────────────────
TruthLens AI — Context / Circumstance Weighting & Interpretation Engine.

Defines circumstance-specific evaluation criteria, target speaking rates,
movement tolerances, category weights, and interpretation rules.

CRITICAL RULE:
Context changes the evaluation criteria. It does NOT invent missing evidence.
If underlying signals are unavailable, the category score remains "Insufficient Data".
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, Any, Optional

from core.constants import (
    CONTEXT_JOB_INTERVIEW,
    CONTEXT_VC_PITCH,
    CONTEXT_CASUAL_MEETING,
    CAT_SPEAKING_STYLE,
    CAT_BODY_LANGUAGE,
    CAT_ENGAGEMENT,
    CAT_CONFIDENCE,
    CAT_STORY_QUALITY,
)


@dataclass(frozen=True)
class ContextProfile:
    key: str
    name: str
    description: str
    target_wpm_min: float
    target_wpm_max: float
    movement_rate_min: float
    movement_rate_max: float
    movement_penalty_threshold: float
    max_acceptable_filler_rate_per_min: float
    category_weights: Dict[str, float]
    interpretation_guidelines: Dict[str, str] = field(default_factory=dict)


PROFILES: Dict[str, ContextProfile] = {
    CONTEXT_JOB_INTERVIEW: ContextProfile(
        key=CONTEXT_JOB_INTERVIEW,
        name="Job Interview",
        description="Structured professional dialogue emphasizing composed pacing, clear narrative structure, and steady eye engagement.",
        target_wpm_min=115.0,
        target_wpm_max=155.0,
        movement_rate_min=15.0,
        movement_rate_max=35.0,
        movement_penalty_threshold=40.0,
        max_acceptable_filler_rate_per_min=2.5,
        category_weights={
            CAT_SPEAKING_STYLE: 0.25,
            CAT_CONFIDENCE: 0.25,
            CAT_STORY_QUALITY: 0.25,
            CAT_BODY_LANGUAGE: 0.15,
            CAT_ENGAGEMENT: 0.10,
        },
        interpretation_guidelines={
            "speaking": "Interview responses benefit from steady, thoughtful pacing allowing the interviewer to digest qualifications.",
            "movement": "Composed posture and measured head movement project attentiveness and professional presence.",
            "story": "Specific chronological examples with clear outcomes (e.g. STAR method) demonstrate competency."
        }
    ),
    CONTEXT_VC_PITCH: ContextProfile(
        key=CONTEXT_VC_PITCH,
        name="VC Pitch Presentation",
        description="High-conviction presentation requiring dynamic engagement, persuasive vocal energy, and crisp focus.",
        target_wpm_min=130.0,
        target_wpm_max=165.0,
        movement_rate_min=12.0,
        movement_rate_max=32.0,
        movement_penalty_threshold=36.0,
        max_acceptable_filler_rate_per_min=1.8,
        category_weights={
            CAT_ENGAGEMENT: 0.25,
            CAT_CONFIDENCE: 0.25,
            CAT_SPEAKING_STYLE: 0.20,
            CAT_BODY_LANGUAGE: 0.15,
            CAT_STORY_QUALITY: 0.15,
        },
        interpretation_guidelines={
            "speaking": "Pitch delivery requires brisk momentum; overly slow cadence may dampen investor excitement.",
            "movement": "Excessive or rapid head shifts can distract from core value propositions during high-stakes presentations.",
            "story": "Concise assertions anchored by verifiable milestones communicate executive clarity."
        }
    ),
    CONTEXT_CASUAL_MEETING: ContextProfile(
        key=CONTEXT_CASUAL_MEETING,
        name="Casual Team Meeting",
        description="Collaborative and informal team discussion with flexible pacing and natural conversational mannerisms.",
        target_wpm_min=100.0,
        target_wpm_max=165.0,
        movement_rate_min=10.0,
        movement_rate_max=45.0,
        movement_penalty_threshold=50.0,
        max_acceptable_filler_rate_per_min=4.0,
        category_weights={
            CAT_SPEAKING_STYLE: 0.20,
            CAT_BODY_LANGUAGE: 0.20,
            CAT_ENGAGEMENT: 0.20,
            CAT_CONFIDENCE: 0.20,
            CAT_STORY_QUALITY: 0.20,
        },
        interpretation_guidelines={
            "speaking": "Conversational flow allows varied speech tempos and informal pauses between team contributions.",
            "movement": "Natural head tilting and relaxed postural shifts are normal and welcome in collaborative settings.",
            "story": "Pragmatic updates and direct points take precedence over rigid narrative formalities."
        }
    ),
}


def get_context_profile(profile_key: Optional[str]) -> ContextProfile:
    """
    Retrieve ContextProfile by key (case-insensitive) or return default Job Interview profile.
    """
    if not profile_key:
        return PROFILES[CONTEXT_JOB_INTERVIEW]

    clean_key = str(profile_key).strip().lower().replace(" ", "_")
    for k, prof in PROFILES.items():
        if clean_key == k or clean_key in prof.name.lower().replace(" ", "_"):
            return prof
    return PROFILES[CONTEXT_JOB_INTERVIEW]
