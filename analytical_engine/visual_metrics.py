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
    # Base movement score derived from distance to context profile reference range.
    # Note: Head movement is a natural component of expressive delivery and is not
    # arbitrarily penalized as nervousness or poor body language.
    m_min = profile.movement_rate_min
    m_max = profile.movement_rate_max

    if m_min <= hm_rate <= m_max:
        posture_score = 94.0
        bl_assessment = f"Your head movement was natural and balanced while speaking ({hm_rate:.1f} movements/min). Movement naturally supports spoken delivery, and your posture remained composed without distracting motion."
        bl_went_well = "Your head movement was steady and naturally supported your speech."
        bl_improv = "Continue using intentional head movement to highlight main transitions in longer presentations."
        bl_rec = "Keep this natural balance, using deliberate nods or movement only when highlighting important points."
    elif hm_rate < m_min:
        # Still delivery — projects composure; slight encouragement for natural movement
        posture_score = max(86.0, 93.0 - (m_min - hm_rate) * 0.4)
        bl_assessment = f"You maintained a composed, still posture with minimal head movement ({hm_rate:.1f} movements/min). While this projects calm composure, adding subtle natural nods can make delivery feel more conversational."
        bl_went_well = "You maintained steady physical composure and consistent camera framing."
        bl_improv = "Allow subtle, natural head shifts when transitioning between ideas so delivery feels relaxed rather than rigid."
        bl_rec = "Allow slight, natural head nods when introducing new ideas so your delivery feels comfortable and expressive."
    else:
        # Active/expressive delivery — non-punitive observational adjustment
        excess = hm_rate - m_max
        # Gentle observational adjustment (not a steep punitive collapse)
        posture_score = max(76.0, 94.0 - (excess * 0.35))
        bl_assessment = f"You demonstrated active, expressive head movement while speaking ({hm_rate:.1f} movements/min). Head movement is a natural aspect of animated delivery; channeling movement purposefully can help emphasize key points without distracting motion."
        bl_went_well = "Your visual delivery was active, expressive, and continuously engaged with the camera."
        bl_improv = "Make head movement intentional rather than continuous, pausing movement during core statements to anchor attention."
        bl_rec = "Don't try to stay completely still. Use head movement when it naturally emphasizes a point, and maintain steady posture when delivering core takeaways."

    # Face presence modifier on body language: leaving camera frame is a legitimate framing issue
    if face_ratio < 0.85:
        posture_score -= (0.85 - face_ratio) * 45.0
        bl_assessment += f" In addition, face visibility dropped to {face_ratio:.0%}; keeping centered within camera framing ensures consistent viewer connection."

    final_bl_score = int(round(max(35.0, min(96.0, posture_score))))

    bl_evidence = f"Supporting data: {hm_rate:.1f} movements/min observed (reference guideline: {m_min:.0f}-{m_max:.0f}/min, non-punitive descriptive guide) | Face presence: {face_ratio:.0%} | Blinks: {blinks}"

    body_language = {
        "score": final_bl_score,
        "head_movement_count": hm_count,
        "head_movement_rate_per_min": round(hm_rate, 1),
        "face_presence_ratio": round(face_ratio, 2),
        "blink_count": blinks,
        "assessment": bl_assessment,
        "evidence_observation": bl_evidence,
        "what_went_well": bl_went_well,
        "what_needs_improvement": bl_improv,
        "practical_recommendation": bl_rec
    }

    # ─────────────────────────────────────────────────────────────────────────
    # 2. CAMERA PRESENCE & FACE VISIBILITY EVALUATION
    # ─────────────────────────────────────────────────────────────────────────
    # Derived directly from face presence ratio (percentage of frames face was in viewport).
    # CRITICAL: This metric measures camera face presence and framing only.
    # It does NOT measure eye contact, gaze fixation, or psychological engagement.
    base_eng = face_ratio * 92.0

    # Observational framing stability adjustment
    stability_bonus = 3.0 if hm_rate <= m_max else max(-6.0, -((hm_rate - m_max) * 0.15))
    raw_eng = base_eng + stability_bonus
    final_eng_score = int(round(max(35.0, min(96.0, raw_eng))))

    if face_ratio >= 0.90:
        eng_assessment = (
            f"Your face remained visible in {face_ratio:.0%} of the analyzed frames. "
            "This metric evaluates camera framing and face visibility; it does not measure eye gaze, eye contact, or internal audience connection."
        )
        eng_went_well = f"Face visibility was maintained across {face_ratio:.0%} of analyzed frames."
        eng_improv = "Maintain this centered framing with your camera positioned at eye level."
        eng_rec = "Position your camera directly at eye level about an arm's length away so your framing stays steady and centered."
    else:
        eng_assessment = (
            f"Your face was detected in {face_ratio:.0%} of the analyzed frames, dipping out of camera framing at points. "
            "Keeping yourself continuously centered ensures clear visual connection (evaluates camera presence, not eye contact)."
        )
        eng_went_well = f"Face visibility was captured during {face_ratio:.0%} of the analyzed portion."
        eng_improv = "Keep your face continuously framed within the camera viewport throughout your delivery."
        eng_rec = "Adjust your chair or camera height so your face remains centered in the upper-middle third of the frame."

    eng_evidence = (
        f"Supporting data: {face_ratio:.0%} face visibility (percentage of frames with face detected in camera viewport) | "
        f"Tracking reliability: {reliability} (measures camera presence, not eye contact or internal engagement)"
    )

    engagement = {
        "score": final_eng_score,
        "metric_name": "Camera Presence",
        "face_presence_ratio": round(face_ratio, 2),
        "assessment": eng_assessment,
        "evidence_observation": eng_evidence,
        "what_went_well": eng_went_well,
        "what_needs_improvement": eng_improv,
        "practical_recommendation": eng_rec
    }

    return body_language, engagement
