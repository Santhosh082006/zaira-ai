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
        bl_assessment = "Your head movement was natural and balanced while speaking. Some movement is natural and makes your delivery feel expressive, and your posture stayed engaged without distracting motion."
        bl_went_well = "Your head movement was steady and naturally supported your speech."
        bl_improv = "Continue using intentional head movement to highlight main transitions in longer presentations."
        bl_rec = "Keep this natural balance, using deliberate nods or movement only when highlighting important points."
    elif hm_rate < m_min:
        # Very low movement — still composed, slight stiffness penalty if near zero
        posture_score = max(78.0, 92.0 - (m_min - hm_rate) * 1.0)
        bl_assessment = "You remained very still with minimal head movement throughout your delivery. While this shows composure, adding slight natural movement can make your delivery feel more relaxed and conversational."
        bl_went_well = "You maintained steady composure and consistent camera presence throughout."
        bl_improv = "Allow subtle, natural head shifts when transitioning between ideas so your delivery feels relaxed rather than rigid."
        bl_rec = "Allow slight, natural head nods when introducing new ideas so your delivery feels comfortable and expressive."
    else:
        # High movement frequency
        excess = hm_rate - m_max
        penalty_rate = 1.6 if hm_rate > p_thresh else 1.1
        posture_score = max(35.0, 94.0 - (excess * penalty_rate))
        bl_assessment = "You used a lot of head movement while speaking. Some movement is natural and can make your delivery feel expressive, but the amount observed was quite high. Making your movements more intentional could make your presentation feel more controlled."
        bl_went_well = "Your face visibility remained consistent and your delivery felt active and expressive."
        bl_improv = "Make your head movements more intentional rather than continuous, helping your audience focus on your message."
        bl_rec = "Don't try to stay completely still. Instead, use head movement when it naturally supports your point and reduce repeated movement when it doesn't."

    # Face presence modifier on body language
    if face_ratio < 0.85:
        posture_score -= (0.85 - face_ratio) * 40.0
        bl_assessment += " You also moved outside the camera frame at times; keeping centered will ensure continuous connection with your audience."

    final_bl_score = int(round(max(35.0, min(96.0, posture_score))))

    bl_evidence = f"Supporting data: {hm_rate:.1f} movements/min (reference: {m_min:.0f}-{m_max:.0f}/min) | Face presence: {face_ratio:.0%} | Blinks: {blinks}"

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
    # 2. ENGAGEMENT & CAMERA PRESENCE EVALUATION
    # ─────────────────────────────────────────────────────────────────────────
    # Derived directly from face presence ratio and visual continuity
    # Note: Eye contact is unmeasured by the current visual pipeline; metric reflects camera face visibility.
    base_eng = face_ratio * 92.0

    # Small stability bonus if movement was not excessively distracting
    stability_bonus = 4.0 if hm_rate <= m_max else max(-10.0, -((hm_rate - m_max) * 0.4))
    raw_eng = base_eng + stability_bonus
    final_eng_score = int(round(max(35.0, min(96.0, raw_eng))))

    if face_ratio >= 0.90:
        eng_assessment = "You maintained consistent camera face visibility throughout your delivery. Staying centered in the frame helps your listeners feel connected and focused on what you are saying."
        eng_went_well = f"Face visibility was consistent during {face_ratio:.0%} of the analyzed portion."
        eng_improv = "Maintain this centered framing and keep your camera at eye level."
        eng_rec = "Position your camera directly at eye level about an arm's length away so your gaze stays naturally directed forward."
    else:
        eng_assessment = "Your face dipped out of the camera frame at points during the recording. Keeping yourself continuously centered in frame ensures your audience stays connected to your delivery."
        eng_went_well = f"Face visibility was captured during {face_ratio:.0%} of the analyzed portion."
        eng_improv = "Keep your face continuously framed within the camera viewport throughout your delivery."
        eng_rec = "Adjust your chair or camera height so your face remains in the upper-middle third of the frame without drifting off-camera."

    eng_evidence = f"Supporting data: {face_ratio:.0%} face visibility | Tracking reliability: {reliability} (metric reflects camera face presence)"

    engagement = {
        "score": final_eng_score,
        "face_presence_ratio": round(face_ratio, 2),
        "assessment": eng_assessment,
        "evidence_observation": eng_evidence,
        "what_went_well": eng_went_well,
        "what_needs_improvement": eng_improv,
        "practical_recommendation": eng_rec
    }

    return body_language, engagement
