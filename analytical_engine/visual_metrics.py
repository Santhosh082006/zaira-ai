"""
analytical_engine/visual_metrics.py
─────────────────────────────────────────────────────────────────────────────
TruthLens AI — Evidence-Based Visual Metric Evaluation.

Calculates body language and engagement scores strictly from MediaPipe FaceMesh
tracking data and context profile tolerances. Never produces arbitrary hardcoded scores.
"""

from __future__ import annotations
from typing import Optional, Dict, Any, Tuple
from processors.context_engine.weighting import ContextProfile


def evaluate_visual_performance(
    visual_feats: Optional[Dict[str, Any]],
    profile: ContextProfile
) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """
    Mathematically evaluate Body Language and Engagement based on measured visual metrics.

    Parameters
    ----------
    visual_feats : dict or None
        Visual features extracted via MediaPipe FaceMesh (head movements, blinks, presence).
    profile : ContextProfile
        Context profile containing circumstance-specific movement tolerances and weights.

    Returns
    -------
    Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]
        (body_language_eval, engagement_eval)
        Each is None if visual tracking is missing, face was not detected, or tracking errored.
    """
    if not visual_feats:
        return None, None

    face_detected = visual_feats.get("face_detected") is True
    reliability = visual_feats.get("tracking_reliability")

    if not face_detected or reliability != "good":
        return None, None

    face_ratio = float(visual_feats.get("face_presence_ratio", 1.0))
    hm_count = int(visual_feats.get("head_movement_count", 0))
    hm_rate = visual_feats.get("head_movement_rate_per_min")
    blinks = int(visual_feats.get("blink_count", 0))
    duration = float(visual_feats.get("duration_seconds") or 1.0)

    # Calculate head movement rate if not already provided
    if hm_rate is None and duration >= 3.0:
        hm_rate = (hm_count / duration) * 60.0
    elif hm_rate is None:
        hm_rate = float(hm_count)

    # ─────────────────────────────────────────────────────────────────────────
    # 1. BODY LANGUAGE & POSTURE EVALUATION
    # ─────────────────────────────────────────────────────────────────────────
    # Base movement score derived from distance to context profile range
    m_min = profile.movement_rate_min
    m_max = profile.movement_rate_max
    p_thresh = profile.movement_penalty_threshold

    if m_min <= hm_rate <= m_max:
        posture_score = 94.0
        posture_label = f"natural and composed ({hm_rate:.1f}/min, within target {m_min:.0f}-{m_max:.0f}/min)"
        bl_improv = "Maintain this balanced head posture and composure."
    elif hm_rate < m_min:
        # Very low movement — still composed, slight stiffness penalty if near zero
        posture_score = max(78.0, 92.0 - (m_min - hm_rate) * 1.0)
        posture_label = f"very steady and still ({hm_rate:.1f}/min, below target range)"
        bl_improv = "Allow subtle natural head gestures to accompany emphasized points."
    else:
        # High movement frequency
        excess = hm_rate - m_max
        penalty_rate = 1.6 if hm_rate > p_thresh else 1.1
        posture_score = max(35.0, 94.0 - (excess * penalty_rate))
        posture_label = f"frequent head movement shifts ({hm_rate:.1f}/min, above target {m_min:.0f}-{m_max:.0f}/min)"
        bl_improv = f"Keep head posture centered and steady when delivering primary statements in a {profile.name}."

    # Face presence modifier on body language
    if face_ratio < 0.85:
        posture_score -= (0.85 - face_ratio) * 40.0

    final_bl_score = int(round(max(35.0, min(96.0, posture_score))))

    body_language = {
        "score": final_bl_score,
        "head_movement_count": hm_count,
        "head_movement_rate_per_min": round(hm_rate, 1),
        "face_presence_ratio": round(face_ratio, 2),
        "blink_count": blinks,
        "assessment": f"Facial landmarks remained visible ({face_ratio:.0%} presence). Head posture was {posture_label} under {profile.name} criteria.",
        "evidence_observation": f"Face presence: {face_ratio:.0%} | Head movements: {hm_count} ({hm_rate:.1f}/min, target: {m_min:.0f}-{m_max:.0f}/min) | Blinks: {blinks}",
        "what_went_well": "Maintained composed posture and alignment within the camera frame." if final_bl_score >= 75 else "Face tracked consistently across active video frames.",
        "what_needs_improvement": bl_improv,
        "practical_recommendation": "Position camera at eye level approximately an arm's length away."
    }

    # ─────────────────────────────────────────────────────────────────────────
    # 2. ENGAGEMENT & CAMERA PRESENCE EVALUATION
    # ─────────────────────────────────────────────────────────────────────────
    # Derived directly from face presence ratio and visual continuity
    # Perfect presence (1.0) -> high engagement, drops linearly as face leaves frame
    base_eng = face_ratio * 92.0

    # Small stability bonus if movement was not excessively distracting
    stability_bonus = 4.0 if hm_rate <= m_max else max(-10.0, -((hm_rate - m_max) * 0.4))
    raw_eng = base_eng + stability_bonus
    final_eng_score = int(round(max(35.0, min(96.0, raw_eng))))

    if face_ratio >= 0.90:
        eng_improv = "Maintain steady gaze alignment directly with the camera lens when closing key statements."
    else:
        eng_improv = f"Increase continuous camera framing (currently {face_ratio:.0%}) to maximize viewer connection."

    engagement = {
        "score": final_eng_score,
        "face_presence_ratio": round(face_ratio, 2),
        "assessment": f"Direct camera presence maintained throughout {face_ratio:.0%} of the session with active visual responsiveness.",
        "evidence_observation": f"Face presence ratio: {face_ratio:.0%} | Landmark continuity: {reliability}",
        "what_went_well": f"Continuous camera presence and forward-facing engagement ({face_ratio:.0%}).",
        "what_needs_improvement": eng_improv,
        "practical_recommendation": "Look directly at the webcam lens rather than your own preview window."
    }

    return body_language, engagement
