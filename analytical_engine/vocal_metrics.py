"""
analytical_engine/vocal_metrics.py
─────────────────────────────────────────────────────────────────────────────
TruthLens AI — Evidence-Based Vocal & Speech Metric Evaluation.

Calculates speaking style and fluency scores strictly from acoustic measurements
and context target ranges. Never produces arbitrary hardcoded scores.
"""

from __future__ import annotations
from typing import Optional, Dict, Any
from processors.context_engine.weighting import ContextProfile


def evaluate_vocal_performance(
    speech_feats: Optional[Dict[str, Any]],
    profile: ContextProfile
) -> Optional[Dict[str, Any]]:
    """
    Mathematically evaluate vocal delivery based on measured acoustic metrics.

    Parameters
    ----------
    speech_feats : dict or None
        Acoustic features extracted by librosa (WPM, pauses, fillers, pitch, energy).
    profile : ContextProfile
        Context profile containing circumstance-specific target ranges and weights.

    Returns
    -------
    dict or None
        Calculated score and acoustic breakdown, or None if signals are unmeasured.
    """
    if not speech_feats:
        return None

    duration = speech_feats.get("duration_seconds")
    wpm = speech_feats.get("speaking_rate_wpm")
    reliability = speech_feats.get("reliability_flag")

    # Guard: Require measurable duration and good acoustic reliability
    if duration is None or duration <= 0 or wpm is None or reliability != "good":
        return None

    # Guard: Extremely low speech detection (e.g. background hiss)
    if wpm <= 15:
        return None

    pauses = int(speech_feats.get("pause_count") or 0)
    pause_sec = float(speech_feats.get("total_pause_duration_sec") or 0.0)
    fillers = int(speech_feats.get("filler_word_count") or 0)

    # 1. Pacing score relative to context target
    t_min = profile.target_wpm_min
    t_max = profile.target_wpm_max

    if t_min <= wpm <= t_max:
        wpm_score = 95.0
        cadence = "well-paced and conversational"
    elif wpm < t_min:
        deficit = t_min - wpm
        wpm_score = max(35.0, 95.0 - (deficit * 1.5))
        cadence = "deliberate and slow" if deficit > 30 else "measured and relaxed"
    else:
        excess = wpm - t_max
        wpm_score = max(35.0, 95.0 - (excess * 1.2))
        cadence = "rapid and hurried" if excess > 30 else "brisk and dynamic"

    # 2. Pause discipline penalty
    pause_ratio = pause_sec / max(1.0, duration)
    pause_penalty = 0.0
    if pause_ratio > 0.35:
        # Over 35% of recording spent in silence/pauses
        pause_penalty = min(20.0, (pause_ratio - 0.35) * 60.0)
    elif pauses == 0 and duration >= 10.0:
        # Continuous breathless delivery without breathing pauses
        pause_penalty = 8.0

    # 3. Filler word density penalty
    fillers_per_min = (fillers / max(1.0, duration)) * 60.0
    filler_penalty = 0.0
    if fillers_per_min > profile.max_acceptable_filler_rate_per_min:
        filler_penalty = min(
            25.0,
            (fillers_per_min - profile.max_acceptable_filler_rate_per_min) * 5.5
        )

    # Final combined score strictly within bounds [35, 96]
    raw_final = wpm_score - pause_penalty - filler_penalty
    final_score = int(round(max(35.0, min(96.0, raw_final))))

    # Observations and advice based on measurements
    if fillers > 2:
        improv = f"Reduce filler words ({fillers} detected, {fillers_per_min:.1f}/min) and smooth phrasing."
    elif wpm < t_min:
        improv = f"Increase speaking tempo toward the target {t_min:.0f}-{t_max:.0f} WPM range for {profile.name}."
    elif wpm > t_max:
        improv = f"Moderate speaking pace down toward the target {t_min:.0f}-{t_max:.0f} WPM range."
    elif pause_ratio > 0.30:
        improv = "Tighten transitions between thoughts to reduce extended silent pauses."
    else:
        improv = "Maintain this natural cadence and vocal pacing."

    if final_score >= 82:
        went_well = f"Excellent vocal cadence ({wpm:.0f} WPM) well-aligned with {profile.name} expectations."
    else:
        went_well = f"Identifiable vocal cadence ({wpm:.0f} WPM) with clear acoustic tracking."

    return {
        "score": final_score,
        "speaking_rate_wpm": round(wpm, 1),
        "cadence_label": cadence,
        "pause_count": pauses,
        "pause_duration_sec": round(pause_sec, 1),
        "filler_count": fillers,
        "filler_rate_per_min": round(fillers_per_min, 1),
        "assessment": f"Vocal cadence was {cadence} ({wpm:.0f} WPM) with {pauses} pauses ({pause_sec:.1f}s) and {fillers} filler words under {profile.name} criteria.",
        "evidence_observation": f"Speaking rate: {wpm:.0f} WPM (target: {t_min:.0f}-{t_max:.0f}) | Pauses: {pauses} ({pause_sec:.1f}s) | Fillers: {fillers}",
        "what_went_well": went_well,
        "what_needs_improvement": improv,
        "practical_recommendation": "Use brief silent breaths rather than vocal fillers when moving between thoughts."
    }
