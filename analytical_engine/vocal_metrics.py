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

    # Guard: Extremely short audio or minimal words has high variance and cannot support stable pacing evaluation
    word_count = int(speech_feats.get("word_count") or 0)
    if duration < 3.0 or word_count < 4:
        return None

    pauses = int(speech_feats.get("pause_count") or 0)
    pause_sec = float(speech_feats.get("total_pause_duration_sec") or 0.0)
    fillers = int(speech_feats.get("filler_word_count") or 0)

    # 1. Pacing score relative to context target (heuristic reference guideline)
    t_min = profile.target_wpm_min
    t_max = profile.target_wpm_max

    if t_min <= wpm <= t_max:
        wpm_score = 95.0
        cadence = "well-paced within reference guideline"
    elif wpm < t_min:
        deficit = t_min - wpm
        # Gradual heuristic adjustment; deliberate cadence is not severely penalized
        wpm_score = max(65.0, 95.0 - (deficit * 0.75))
        cadence = "deliberate pace" if deficit > 30 else "relaxed pacing"
    else:
        excess = wpm - t_max
        # Gradual heuristic adjustment; energetic speech is not severely penalized
        wpm_score = max(65.0, 95.0 - (excess * 0.65))
        cadence = "rapid pace" if excess > 30 else "brisk pacing"

    # 2. Pause discipline penalty
    pause_ratio = pause_sec / max(1.0, duration)
    pause_penalty = 0.0
    if pause_ratio > 0.35:
        # Over 35% of recording spent in silence/pauses
        pause_penalty = min(20.0, (pause_ratio - 0.35) * 60.0)
    elif pauses == 0 and duration >= 15.0:
        # Continuous delivery without natural breathing pauses (evaluated over >=15s)
        pause_penalty = 6.0

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

    # Human-friendly coaching review answering:
    # 1. What did I do? (in clear, non-technical terms)
    # 2. Why might it matter? (impact on listener engagement)
    # 3. What can I improve? (focus area)
    # 4. How should I practice it? ("Try this" actionable technique)

    # Primary Assessment (What did I do & why it matters)
    # Note: Speaking rate targets are heuristic reference guidelines, not absolute scientific rules.
    if t_min <= wpm <= t_max:
        if pauses == 0 and duration >= 15.0:
            assessment = f"Your speaking pace was steady and continuous ({wpm:.0f} WPM, within the {t_min:.0f}-{t_max:.0f} WPM heuristic reference guideline). Adding brief pauses will help listeners digest key points."
        else:
            assessment = f"Your speaking pace was steady and comfortable ({wpm:.0f} WPM, aligning with the {t_min:.0f}-{t_max:.0f} WPM heuristic guideline), giving your listener time to absorb your thoughts."
    elif wpm < t_min:
        assessment = f"You spoke at an unhurried, deliberate pace ({wpm:.0f} WPM, below the {t_min:.0f}-{t_max:.0f} WPM heuristic guideline). A deliberate cadence can aid clarity for complex explanations; picking up the tempo slightly can help maintain dynamic momentum."
    else:
        assessment = f"You spoke at a brisk pace ({wpm:.0f} WPM, above the {t_min:.0f}-{t_max:.0f} WPM heuristic guideline). While this conveys dynamism, giving listeners an occasional moment between complex points aids absorption."

    # What went well (Strengths)
    if pauses == 0 and duration >= 15.0:
        went_well = "Your speaking pace was steady and continuous without hesitation."
    elif t_min <= wpm <= t_max:
        went_well = f"Your speaking pace was conversational ({wpm:.0f} WPM), making your points easy to absorb."
    elif wpm < t_min:
        went_well = "Your words were delivered deliberately and articulated clearly without rushing."
    else:
        went_well = "Your delivery maintained strong momentum and energetic forward pacing."

    # What needs improvement (Focus Area)
    if fillers > 2:
        improv = f"Vocal filler words were used frequently ({fillers} detected). Replacing them with silent pauses will make your delivery sound cleaner and more polished."
    elif wpm < t_min:
        improv = f"Increase your speaking momentum toward a conversational tempo ({t_min:.0f}-{t_max:.0f} WPM guideline) to keep the presentation engaging."
    elif wpm > t_max:
        improv = f"Ease your speaking tempo slightly toward a conversational pace ({t_min:.0f}-{t_max:.0f} WPM guideline) so listeners can absorb complex thoughts effortlessly."
    elif pause_ratio > 0.30:
        improv = "Transitions between thoughts had longer silent gaps than needed. Smoothing these transitions will keep your narrative flowing effortlessly."
    elif pauses == 0 and duration >= 15.0:
        improv = "No long pauses were detected, so deliberate strategic pauses could be introduced to emphasize important points."
    else:
        improv = "Maintain this comfortable, steady speaking pace across longer presentations."

    # Practical recommendation ("💡 Try this")
    if fillers > 2:
        rec = "When you feel the urge to say a filler word like 'um' or 'uh', take a silent breath instead before speaking the next phrase."
    elif wpm < t_min:
        rec = "Practice speaking with slightly more forward energy, linking connected thoughts together without stopping between every phrase."
    elif wpm > t_max:
        rec = "Take a relaxed breath after completing a major thought to naturally pace your delivery and give listeners a moment to reflect."
    elif pauses == 0 and duration >= 15.0:
        rec = "Keep the same comfortable pace, and consider adding short pauses before important points to give them more emphasis."
    else:
        rec = "Keep this steady pace, and use brief strategic pauses right before key points to make them stand out."

    pause_desc = "no long pauses detected" if pauses == 0 else f"{pauses} pauses ({pause_sec:.1f}s)"
    evidence_obs = f"Supporting data: {wpm:.0f} WPM (context target reference: {t_min:.0f}-{t_max:.0f} WPM, heuristic guideline) | {pause_desc} | Fillers: {fillers}"

    return {
        "score": final_score,
        "speaking_rate_wpm": round(wpm, 1),
        "cadence_label": cadence,
        "pause_count": pauses,
        "pause_duration_sec": round(pause_sec, 1),
        "filler_count": fillers,
        "filler_rate_per_min": round(fillers_per_min, 1),
        "assessment": assessment,
        "evidence_observation": evidence_obs,
        "what_went_well": went_well,
        "what_needs_improvement": improv,
        "practical_recommendation": rec
    }
