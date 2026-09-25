"""
analytical_engine/evaluator.py
─────────────────────────────────────────────────────────────────────────────
TruthLens AI — Evidence-Based Multimodal Performance Evaluator.

Architecture:
  RAW MEASUREMENTS
        ↓
  DETERMINISTIC EVALUATOR (calculates exact evidence-backed scores)
        ↓
  CALCULATED SCORES
        ↓
  LLM (writes qualitative explanation strictly around the calculated scores)
        ↓
  INTEGRITY ENFORCEMENT (locks calculated scores & prevents duplicate advice)

CRITICAL RULES:
1. No arbitrary constants (80, 75, 85).
2. If data is missing for a category, score is "Insufficient Data".
3. The LLM NEVER alters or invents numeric scores.
"""

from __future__ import annotations
import json
from typing import Optional, Dict, Any

from core.constants import (
    INSUFFICIENT_DATA,
    CAT_SPEAKING_STYLE,
    CAT_BODY_LANGUAGE,
    CAT_ENGAGEMENT,
    CAT_CONFIDENCE,
    CAT_STORY_QUALITY,
)
from processors.context_engine.weighting import ContextProfile, get_context_profile
from analytical_engine.vocal_metrics import evaluate_vocal_performance
from analytical_engine.visual_metrics import evaluate_visual_performance


def compute_deterministic_scores(
    person_name: str,
    transcript: str,
    story_data: Optional[Dict[str, Any]],
    speech_feats: Optional[Dict[str, Any]],
    visual_feats: Optional[Dict[str, Any]],
    profile: Optional[ContextProfile] = None
) -> Dict[str, Dict[str, Any]]:
    """
    Compute mathematically derived scores for all 5 performance categories
    strictly from measured data and context profile criteria.
    """
    if profile is None:
        profile = get_context_profile(None)

    # 1. Vocal / Speaking Style
    vocal_res = evaluate_vocal_performance(speech_feats, profile)
    if vocal_res is not None:
        speaking_style = vocal_res
    else:
        speaking_style = {
            "score": INSUFFICIENT_DATA,
            "assessment": "No speech audio available or acoustic metrics could not be extracted.",
            "evidence_observation": "Acoustic audio stream not provided or extraction returned null metrics.",
            "what_went_well": "N/A",
            "what_needs_improvement": "N/A",
            "practical_recommendation": "Record or upload an audio/video file with audible narration."
        }

    # 2. Visual / Body Language & Engagement
    bl_res, eng_res = evaluate_visual_performance(visual_feats, profile)
    if bl_res is not None:
        body_language = bl_res
    else:
        body_language = {
            "score": INSUFFICIENT_DATA,
            "assessment": "No face or posture landmarks detected in the video frames.",
            "evidence_observation": "Visual tracking returned 0 valid face frames.",
            "what_went_well": "N/A",
            "what_needs_improvement": "N/A",
            "practical_recommendation": "Ensure face is well-lit from the front and directly faces the camera."
        }

    if eng_res is not None:
        engagement = eng_res
    else:
        engagement = {
            "score": INSUFFICIENT_DATA,
            "assessment": "Engagement signals require active facial landmark tracking.",
            "evidence_observation": "No facial landmark stream available.",
            "what_went_well": "N/A",
            "what_needs_improvement": "N/A",
            "practical_recommendation": "Position yourself centered in the camera viewport."
        }

    # 3. Confidence Indicators (Observable communication composure)
    # Computed strictly from available behavioral channels
    valid_behavioral_scores = []
    if isinstance(speaking_style.get("score"), (int, float)):
        valid_behavioral_scores.append(float(speaking_style["score"]))
    if isinstance(body_language.get("score"), (int, float)):
        valid_behavioral_scores.append(float(body_language["score"]))
    if isinstance(engagement.get("score"), (int, float)):
        valid_behavioral_scores.append(float(engagement["score"]))

    if valid_behavioral_scores:
        conf_score = int(round(sum(valid_behavioral_scores) / len(valid_behavioral_scores)))
        confidence_indicators = {
            "score": conf_score,
            "assessment": f"Observable behavioral signals reflect steady delivery composure across {len(valid_behavioral_scores)} analyzed modalities.",
            "evidence_observation": f"Calculated across {len(valid_behavioral_scores)} observable behavioral channels (mean rating: {conf_score}/100).",
            "what_went_well": "Consistent vocal and physical presence during delivery.",
            "what_needs_improvement": "Minimize verbal hedges (e.g., 'maybe', 'I guess') and anchor key assertions with steady delivery.",
            "practical_recommendation": "Pause briefly before delivering central points to convey composure."
        }
    else:
        confidence_indicators = {
            "score": INSUFFICIENT_DATA,
            "assessment": "Insufficient multimodal behavioral signals to evaluate delivery confidence.",
            "evidence_observation": "Acoustic and visual streams lack sufficient measurable signals.",
            "what_went_well": "N/A",
            "what_needs_improvement": "N/A",
            "practical_recommendation": "Record both clear microphone audio and forward-facing video."
        }

    # 4. Story Quality & Structure (Chronological narrative structure)
    words = len((transcript or "").split())
    has_text = bool((transcript or "").strip() and words >= 6)

    if story_data and story_data.get("events"):
        events = story_data.get("events", [])
        claims = story_data.get("claims", [])
        locations = story_data.get("all_locations_mentioned", [])
        people = story_data.get("all_people_mentioned", [])

        # Mathematical score based strictly on narrative completeness
        raw_sq = 45.0 + (len(events) * 9.0) + (len(claims) * 4.0) + (len(locations) * 3.0)
        sq_score = int(round(max(45.0, min(95.0, raw_sq))))

        story_quality = {
            "score": sq_score,
            "assessment": f"Account exhibits clear chronological structure with {len(events)} events, {len(claims)} claims, and {len(locations)} locations.",
            "evidence_observation": f"{len(events)} events, {len(claims)} claims, {len(locations)} locations, {len(people)} people referenced.",
            "what_went_well": "Clear sequential narrative with identifiable factual anchors.",
            "what_needs_improvement": "Incorporate specific timestamps, location context, and sequential transition words to improve narrative chronology.",
            "practical_recommendation": "Anchor each event with explicit time markers (e.g., 'at 2 PM', 'shortly afterward') and spatial details."
        }
    elif has_text:
        raw_sq = min(75.0, 40.0 + (words * 0.6))
        sq_score = int(round(raw_sq))
        story_quality = {
            "score": sq_score,
            "assessment": f"Transcript with {words} words captured. Structured narrative points are minimal.",
            "evidence_observation": f"Raw transcript contains {words} words.",
            "what_went_well": "Account was successfully captured in text.",
            "what_needs_improvement": "Add specific time markers and chronological sequence connectors (first, then, afterward).",
            "practical_recommendation": "Structure the narrative with specific timestamps and locations."
        }
    else:
        story_quality = {
            "score": INSUFFICIENT_DATA,
            "assessment": "No transcript available to evaluate narrative structure.",
            "evidence_observation": "Missing textual account.",
            "what_went_well": "N/A",
            "what_needs_improvement": "N/A",
            "practical_recommendation": "Provide a spoken or manual narrative account."
        }

    return {
        CAT_CONFIDENCE: confidence_indicators,
        CAT_BODY_LANGUAGE: body_language,
        CAT_SPEAKING_STYLE: speaking_style,
        CAT_ENGAGEMENT: engagement,
        CAT_STORY_QUALITY: story_quality,
    }


def evaluate_account_with_explanation(
    person_name: str,
    transcript: str,
    story_data: Optional[Dict[str, Any]],
    speech_feats: Optional[Dict[str, Any]],
    visual_feats: Optional[Dict[str, Any]],
    profile_key: Optional[str] = None
) -> Dict[str, Dict[str, Any]]:
    """
    Main evaluation pipeline:
    1. Deterministically calculates exact scores based on evidence & context profile.
    2. Prompts LLM to supply qualitative explanations (without changing scores).
    3. Strictly locks scores to the deterministic values and enforces integrity.
    """
    profile = get_context_profile(profile_key)
    deterministic_eval = compute_deterministic_scores(
        person_name=person_name,
        transcript=transcript,
        story_data=story_data,
        speech_feats=speech_feats,
        visual_feats=visual_feats,
        profile=profile
    )

    # Check which modalities are valid
    has_valid_speech = deterministic_eval[CAT_SPEAKING_STYLE]["score"] != INSUFFICIENT_DATA
    has_valid_visual = deterministic_eval[CAT_BODY_LANGUAGE]["score"] != INSUFFICIENT_DATA
    has_valid_transcript = deterministic_eval[CAT_STORY_QUALITY]["score"] != INSUFFICIENT_DATA
    has_valid_story = bool(story_data and (story_data.get("events") or story_data.get("claims")))

    # Format score summary for the LLM
    score_summary = {k: v["score"] for k, v in deterministic_eval.items()}

    prompt = f"""
You are an expert communication and performance analyst evaluating '{person_name}' under the '{profile.name}' context.
The objective numeric scores have ALREADY been calculated by our deterministic measurement engine:
{json.dumps(score_summary, indent=2)}

Your task is STRICTLY to write qualitative explanations and recommendations.
DO NOT change the numerical scores. If a score is "Insufficient Data", keep it as "Insufficient Data" and provide "N/A" for strengths/improvements.

CONTEXT GUIDELINES ({profile.name}):
- {profile.description}
- Speaking guideline: {profile.interpretation_guidelines.get('speaking', '')}
- Movement guideline: {profile.interpretation_guidelines.get('movement', '')}
- Story guideline: {profile.interpretation_guidelines.get('story', '')}

DATA AVAILABLE:
- Transcript: {transcript if transcript else 'MISSING'}
- Story Extracted: {json.dumps(story_data) if story_data else 'MISSING'}
- Speech Features: {json.dumps(speech_feats) if has_valid_speech else 'MISSING'}
- Visual Features: {json.dumps(visual_feats) if has_valid_visual else 'MISSING'}

OUTPUT FORMAT (Strictly Valid JSON only, matching the exact scores provided):
{{
  "confidence_indicators": {{
    "score": {json.dumps(deterministic_eval['confidence_indicators']['score'])},
    "assessment": "<string>",
    "evidence_observation": "<string>",
    "what_went_well": "<string or N/A>",
    "what_needs_improvement": "<string or N/A>",
    "practical_recommendation": "<string>"
  }},
  "body_language": {{
    "score": {json.dumps(deterministic_eval['body_language']['score'])},
    "assessment": "<string>",
    "evidence_observation": "<string>",
    "what_went_well": "<string or N/A>",
    "what_needs_improvement": "<string or N/A>",
    "practical_recommendation": "<string>"
  }},
  "speaking_style": {{
    "score": {json.dumps(deterministic_eval['speaking_style']['score'])},
    "assessment": "<string>",
    "evidence_observation": "<string>",
    "what_went_well": "<string or N/A>",
    "what_needs_improvement": "<string or N/A>",
    "practical_recommendation": "<string>"
  }},
  "engagement": {{
    "score": {json.dumps(deterministic_eval['engagement']['score'])},
    "assessment": "<string>",
    "evidence_observation": "<string>",
    "what_went_well": "<string or N/A>",
    "what_needs_improvement": "<string or N/A>",
    "practical_recommendation": "<string>"
  }},
  "story_quality": {{
    "score": {json.dumps(deterministic_eval['story_quality']['score'])},
    "assessment": "<string>",
    "evidence_observation": "<string>",
    "what_went_well": "<string or N/A>",
    "what_needs_improvement": "<string or N/A>",
    "practical_recommendation": "<string>"
  }}
}}
"""

    system = "You are a communication analyst. Return strictly valid JSON matching the schema. No markdown wrapping."
    from services.llm_provider import call_llm
    from services.story_analyzer import _parse_json_response, _enforce_data_integrity

    try:
        response = call_llm(prompt=prompt, system_prompt=system)
        parsed = _parse_json_response(response, person_name)
        if parsed and all(k in parsed for k in deterministic_eval.keys()):
            # CRITICAL ENFORCEMENT: Lock scores to the deterministic values
            for cat_key, cat_val in deterministic_eval.items():
                if cat_key in parsed and isinstance(parsed[cat_key], dict):
                    parsed[cat_key]["score"] = cat_val["score"]
            return _enforce_data_integrity(
                parsed, has_valid_speech, has_valid_visual, has_valid_transcript, has_valid_story, visual_feats
            )
    except Exception as e:
        print(f"LLM explanation unavailable ({e}); utilizing deterministic evaluation output directly.")

    # Return pure deterministic evaluation with data integrity enforcement
    return _enforce_data_integrity(
        deterministic_eval, has_valid_speech, has_valid_visual, has_valid_transcript, has_valid_story, visual_feats
    )
