"""
analytical_engine/cross_comparator.py
─────────────────────────────────────────────────────────────────────────────
TruthLens AI — Evidence-Based Comparative Performance Engine.

Compares two independently analyzed recordings (Video A and Video B) under
a shared context profile. Computes side-by-side metric deltas and determines
the stronger measured performance strictly via mathematical criteria.

CRITICAL RULES:
1. Both videos must have sufficient comparable data before declaring a winner.
2. Winner declaration is strictly:
   "🏆 Stronger Measured Performance: Video A"
   "🏆 Stronger Measured Performance: Video B"
   "🤝 Comparable Result"
3. NEVER produce deception, lying, truthfulness, or credibility claims.
"""

from __future__ import annotations
from typing import Optional, Dict, Any, List

from core.constants import (
    INSUFFICIENT_DATA,
    CAT_SPEAKING_STYLE,
    CAT_BODY_LANGUAGE,
    CAT_ENGAGEMENT,
    CAT_CONFIDENCE,
    CAT_STORY_QUALITY,
    ALL_CATEGORIES,
)
from processors.context_engine.weighting import ContextProfile, get_context_profile


def compare_multimodal_performance(
    eval_a: Optional[Dict[str, Any]],
    eval_b: Optional[Dict[str, Any]],
    speech_a: Optional[Dict[str, Any]] = None,
    speech_b: Optional[Dict[str, Any]] = None,
    visual_a: Optional[Dict[str, Any]] = None,
    visual_b: Optional[Dict[str, Any]] = None,
    story_a: Optional[Dict[str, Any]] = None,
    story_b: Optional[Dict[str, Any]] = None,
    profile_key: Optional[str] = None,
    label_a: str = "Video A",
    label_b: str = "Video B",
) -> Dict[str, Any]:
    """
    Perform independent side-by-side metric comparison and mathematical winner determination.
    """
    profile = get_context_profile(profile_key)
    eval_a = eval_a or {}
    eval_b = eval_b or {}

    # ─────────────────────────────────────────────────────────────────────────
    # 1. SIDE-BY-SIDE METRIC DELTAS
    # ─────────────────────────────────────────────────────────────────────────
    metric_deltas: List[Dict[str, Any]] = []

    # Speaking Pace (WPM)
    wpm_a = speech_a.get("speaking_rate_wpm") if speech_a else None
    wpm_b = speech_b.get("speaking_rate_wpm") if speech_b else None
    if wpm_a is not None and wpm_b is not None:
        delta_wpm = wpm_b - wpm_a
        metric_deltas.append({
            "metric": "Speaking Pace",
            "val_a": f"{wpm_a:.0f} WPM",
            "val_b": f"{wpm_b:.0f} WPM",
            "delta": f"{'+' if delta_wpm >= 0 else ''}{delta_wpm:.0f} WPM",
            "interpretation": f"{label_b} was {'faster' if delta_wpm > 0 else 'slower'} by {abs(delta_wpm):.0f} WPM (target: {profile.target_wpm_min:.0f}-{profile.target_wpm_max:.0f} WPM)."
        })

    # Pauses
    p_cnt_a = speech_a.get("pause_count") if speech_a else None
    p_cnt_b = speech_b.get("pause_count") if speech_b else None
    if p_cnt_a is not None and p_cnt_b is not None:
        delta_pauses = p_cnt_b - p_cnt_a
        metric_deltas.append({
            "metric": "Pause Count",
            "val_a": f"{p_cnt_a}",
            "val_b": f"{p_cnt_b}",
            "delta": f"{'+' if delta_pauses >= 0 else ''}{delta_pauses}",
            "interpretation": f"{label_b} had {abs(delta_pauses)} {'more' if delta_pauses > 0 else 'fewer'} pauses."
        })

    # Filler Words
    f_cnt_a = speech_a.get("filler_word_count") if speech_a else None
    f_cnt_b = speech_b.get("filler_word_count") if speech_b else None
    if f_cnt_a is not None and f_cnt_b is not None:
        delta_fillers = f_cnt_b - f_cnt_a
        metric_deltas.append({
            "metric": "Filler Words",
            "val_a": f"{f_cnt_a}",
            "val_b": f"{f_cnt_b}",
            "delta": f"{'+' if delta_fillers >= 0 else ''}{delta_fillers}",
            "interpretation": f"{label_b} used {abs(delta_fillers)} {'more' if delta_fillers > 0 else 'fewer'} fillers."
        })

    # Head Movement Rate
    hm_rate_a = visual_a.get("head_movement_rate_per_min") if visual_a else None
    hm_rate_b = visual_b.get("head_movement_rate_per_min") if visual_b else None
    if hm_rate_a is not None and hm_rate_b is not None:
        delta_hm = hm_rate_b - hm_rate_a
        metric_deltas.append({
            "metric": "Head Movement Rate",
            "val_a": f"{hm_rate_a:.1f}/min",
            "val_b": f"{hm_rate_b:.1f}/min",
            "delta": f"{'+' if delta_hm >= 0 else ''}{delta_hm:.1f}/min",
            "interpretation": f"{label_b} shifted posture {abs(delta_hm):.1f}/min {'more frequently' if delta_hm > 0 else 'less frequently'} (reference: {profile.movement_rate_min:.0f}-{profile.movement_rate_max:.0f}/min, descriptive observation)."
        })

    # Face Presence Ratio
    fp_a = visual_a.get("face_presence_ratio") if visual_a else None
    fp_b = visual_b.get("face_presence_ratio") if visual_b else None
    if fp_a is not None and fp_b is not None:
        delta_fp = (fp_b - fp_a) * 100.0
        metric_deltas.append({
            "metric": "Camera Presence",
            "val_a": f"{fp_a:.0%}",
            "val_b": f"{fp_b:.0%}",
            "delta": f"{'+' if delta_fp >= 0 else ''}{delta_fp:.1f}%",
            "interpretation": f"{label_b} maintained {abs(delta_fp):.1f}% {'higher' if delta_fp > 0 else 'lower'} face presence in camera viewport."
        })

    # ─────────────────────────────────────────────────────────────────────────
    # 2. CATEGORY SCORE DELTAS
    # ─────────────────────────────────────────────────────────────────────────
    category_comparisons: List[Dict[str, Any]] = []
    comparable_categories: List[str] = []
    weighted_score_a = 0.0
    weighted_score_b = 0.0
    total_active_weight = 0.0
    factors_responsible: List[str] = []

    CATEGORY_TITLE_MAP = {
        CAT_STORY_QUALITY: "Narrative Detail",
        CAT_ENGAGEMENT: "Camera Presence",
        CAT_CONFIDENCE: "Delivery Composure",
        CAT_SPEAKING_STYLE: "Speaking Style",
        CAT_BODY_LANGUAGE: "Body Language",
    }

    for cat in ALL_CATEGORIES:
        score_a_raw = eval_a.get(cat, {}).get("score")
        score_b_raw = eval_b.get(cat, {}).get("score")

        weight = profile.category_weights.get(cat, 0.20)
        cat_title = CATEGORY_TITLE_MAP.get(cat, cat.replace("_", " ").title())

        is_a_numeric = isinstance(score_a_raw, (int, float))
        is_b_numeric = isinstance(score_b_raw, (int, float))

        if is_a_numeric and is_b_numeric:
            s_a = float(score_a_raw)
            s_b = float(score_b_raw)
            diff = s_b - s_a
            comparable_categories.append(cat)
            weighted_score_a += s_a * weight
            weighted_score_b += s_b * weight
            total_active_weight += weight

            if abs(diff) >= 4:
                leader = label_b if diff > 0 else label_a
                factors_responsible.append(
                    f"{leader} scored {abs(diff):.0f} points higher in {cat_title} ({s_b:.0f} vs {s_a:.0f})."
                )

            category_comparisons.append({
                "category": cat_title,
                "score_a": int(s_a),
                "score_b": int(s_b),
                "delta": f"{'+' if diff >= 0 else ''}{int(diff)}",
                "weight": f"{weight:.0%}",
                "status": f"{label_b} higher" if diff > 2 else (f"{label_a} higher" if diff < -2 else "Comparable")
            })
        else:
            category_comparisons.append({
                "category": cat_title,
                "score_a": score_a_raw if score_a_raw is not None else INSUFFICIENT_DATA,
                "score_b": score_b_raw if score_b_raw is not None else INSUFFICIENT_DATA,
                "delta": "N/A",
                "weight": f"{weight:.0%}",
                "status": "Incomplete Data"
            })

    # ─────────────────────────────────────────────────────────────────────────
    # 3. MATHEMATICAL WINNER DETERMINATION
    # ─────────────────────────────────────────────────────────────────────────
    # Only declare when BOTH have sufficient comparable categories (at least 2)
    if len(comparable_categories) >= 2 and total_active_weight > 0:
        norm_score_a = weighted_score_a / total_active_weight
        norm_score_b = weighted_score_b / total_active_weight
        score_diff = norm_score_b - norm_score_a

        if score_diff >= 3.0:
            winner = label_b
            outcome_badge = f"🏆 Stronger Measured Performance: {label_b}"
            explanation = (
                f"{label_b} demonstrated stronger overall measured performance under {profile.name} criteria "
                f"(composite rating: {norm_score_b:.1f} vs {norm_score_a:.1f}). "
                + " ".join(factors_responsible[:3])
            )
        elif score_diff <= -3.0:
            winner = label_a
            outcome_badge = f"🏆 Stronger Measured Performance: {label_a}"
            explanation = (
                f"{label_a} demonstrated stronger overall measured performance under {profile.name} criteria "
                f"(composite rating: {norm_score_a:.1f} vs {norm_score_b:.1f}). "
                + " ".join(factors_responsible[:3])
            )
        else:
            winner = "Comparable"
            outcome_badge = "🤝 Comparable Result"
            explanation = (
                f"Both recordings displayed comparable measured performance under {profile.name} criteria "
                f"({norm_score_a:.1f} vs {norm_score_b:.1f}, margin: {abs(score_diff):.1f} points). "
                f"Delivery strengths were evenly balanced across the {len(comparable_categories)} evaluated modalities."
            )
    else:
        winner = None
        outcome_badge = "⚪ Insufficient Comparable Data"
        explanation = (
            f"Both {label_a} and {label_b} must have at least 2 comparable scored categories to declare a comparative result. "
            f"Currently, only {len(comparable_categories)} categories have sufficient data on both sides."
        )

    # ─────────────────────────────────────────────────────────────────────────
    # 4. STORY FACTS & TIMELINE COMPARISON (if available)
    # ─────────────────────────────────────────────────────────────────────────
    story_comparison = None
    if story_a and story_b:
        try:
            from services.story_comparator import compare_stories
            story_comparison = compare_stories(story_a, story_b)
        except Exception as err:
            story_comparison = {"error": str(err)}

    return {
        "context_profile": profile.name,
        "winner": winner,
        "outcome_badge": outcome_badge,
        "explanation": explanation,
        "metric_deltas": metric_deltas,
        "category_comparisons": category_comparisons,
        "comparable_categories_count": len(comparable_categories),
        "factors_responsible": factors_responsible,
        "story_comparison": story_comparison,
    }
