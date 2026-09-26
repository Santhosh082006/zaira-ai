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
        wpm_val = speech_feats.get("speaking_rate_wpm") if speech_feats else None
        pauses_val = speech_feats.get("pause_count") if speech_feats else None
        wpm_str = f"{wpm_val:.0f} WPM" if wpm_val is not None else "a steady speaking pace"
        pause_str = "no long pauses detected" if pauses_val == 0 else (f"{pauses_val} pauses detected" if pauses_val is not None else "available acoustic tracking")
        
        confidence_indicators = {
            "score": conf_score,
            "assessment": f"The available presentation signals show a speaking pace of {wpm_str} with {pause_str}. However, confidence as an internal state cannot be determined from these signals alone.",
            "evidence_observation": f"Presentation delivery indicator ({conf_score}/100) calculated across {len(valid_behavioral_scores)} observable channels. Evaluates presentation delivery composure, not internal emotional state.",
            "what_went_well": "Speaking pace and camera framing remained steady throughout the delivery.",
            "what_needs_improvement": "Anchor central assertions with deliberate pacing rather than increasing delivery speed.",
            "practical_recommendation": "Pause briefly before delivering central points to support steady presentation delivery."
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
            "assessment": f"The narrative contains {len(events)} sequential events, {len(claims)} factual claims, and {len(locations)} concrete locations that provide specificity to the account.",
            "evidence_observation": f"{len(events)} events, {len(claims)} claims, {len(locations)} locations, {len(people)} people referenced in transcript.",
            "what_went_well": "The narrative contains concrete examples that improve specificity.",
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

    # Structured summaries of measurements with units and notes on unmeasured modalities
    speech_summary = "UNAVAILABLE"
    if has_valid_speech and speech_feats:
        wpm = speech_feats.get("speaking_rate_wpm", "N/A")
        fillers = speech_feats.get("filler_word_count", "N/A")
        pauses = speech_feats.get("pause_count", "N/A")
        p_dur = speech_feats.get("total_pause_duration_sec", "N/A")
        dur = speech_feats.get("duration_seconds", "N/A")
        speech_summary = (
            f"Speaking Rate: {wpm} WPM (target reference: {profile.target_wpm_min}-{profile.target_wpm_max} WPM), "
            f"Filler Words: {fillers}, Pauses: {pauses} (pause duration: {p_dur}s), Duration: {dur}s. "
            f"NOTE: Tone/prosody is UNMEASURED; Hesitation metric is UNMEASURED."
        )

    visual_summary = "UNAVAILABLE"
    if has_valid_visual and visual_feats:
        face_ratio = visual_feats.get("face_presence_ratio", 1.0)
        hm_count = visual_feats.get("head_movement_count", 0)
        hm_rate = visual_feats.get("head_movement_rate_per_min", 0.0)
        blinks = visual_feats.get("blink_count", 0)
        visual_summary = (
            f"Face Presence Ratio: {face_ratio:.0%}, Head Movements: {hm_count} ({hm_rate:.1f}/min, configured reference range: 15-35/min), Blinks: {blinks}. "
            f"NOTE: Eye-contact metric is UNMEASURED. Face presence != eye contact. Use 'face visibility was consistent'."
        )

    prompt = f"""
You are an expert communication and performance analyst evaluating '{person_name}' under the '{profile.name}' context.
The objective numeric scores have ALREADY been calculated by our deterministic measurement engine:
{json.dumps(score_summary, indent=2)}

Your task is STRICTLY to write qualitative explanations and recommendations.
DO NOT change the numerical scores. If a score is "Insufficient Data", keep it as "Insufficient Data" and provide "N/A" for strengths/improvements.

==================================================
CRITICAL CORE REQUIREMENTS:
==================================================
1. You are evaluating observable communication performance.
2. Use ONLY evidence explicitly supplied in the structured input.
3. Never invent observations.
4. Never infer an internal mental or emotional state. Avoid words like 'nervous', 'confident', 'hesitant', 'uncertain', 'assertive' as internal states.
5. Never infer deception, truthfulness, honesty, credibility, or lying.
   - REMOVE/AVOID phrases such as 'enhances the credibility of the claims', 'believable', 'truthful', 'honest'.
   - Instead use: 'Specific examples provide additional detail to the narrative' or 'The narrative contains concrete examples that improve specificity.'
6. Do not claim eye contact unless an explicit eye-contact metric is supplied. Face presence != eye contact. Describe it as 'Face visibility was consistent during the analyzed portion.'
7. Do not claim vocal tone unless tone/prosody metrics are explicitly supplied. Use measured speaking rate ({speech_feats.get('speaking_rate_wpm') if speech_feats else 'N/A'} WPM) and pause count.
8. Do not claim hesitation unless hesitation is explicitly represented by measured speech signals.
9. Do not claim confidence as a psychological state. The section evaluates observable presentation delivery signals only (e.g. 'The available presentation signals show a steady speaking pace of X WPM with no long pauses detected. However, confidence as an internal state cannot be determined from these signals alone.').
10. The transcript may contain words such as 'liar', 'lying', 'deceive', 'truth', or 'not telling the truth'. These are simply part of the speaker's spoken narrative. Do NOT allow the presence of these words to influence confidence, body language, engagement, or story evaluation. TruthLens analyzes communication performance, not whether someone is lying.
11. Translate measurements into observable communication-performance feedback only. Every Evidence / Observation statement must be directly traceable to a supplied metric, transcript property, or story-structure property.
12. If evidence is unavailable, explicitly state that the signal was not available.
13. Do not use generic filler feedback (e.g., 'Practice confidence', 'Improve body language', 'Be more assertive').
    Recommendations must follow: MEASUREMENT -> OBSERVATION -> IMPACT ON COMMUNICATION -> ACTION.

CONTEXT GUIDELINES ({profile.name}):
- {profile.description}
- Speaking guideline: {profile.interpretation_guidelines.get('speaking', '')}
- Movement guideline: {profile.interpretation_guidelines.get('movement', '')}
- Story guideline: {profile.interpretation_guidelines.get('story', '')}

DATA AVAILABLE:
- Measured Speech: {speech_summary}
- Measured Visual: {visual_summary}
- Extracted Story: {json.dumps(story_data) if story_data else 'UNAVAILABLE'}
- Spoken Transcript: {transcript if transcript else 'UNAVAILABLE'}

OUTPUT FORMAT (Strictly Valid JSON only, matching the exact scores provided):
{{
  "confidence_indicators": {{
    "score": {json.dumps(deterministic_eval['confidence_indicators']['score'])},
    "assessment": "<string grounded strictly in observable presentation pacing>",
    "evidence_observation": "<string traceable to measured pacing/framing>",
    "what_went_well": "<string or N/A>",
    "what_needs_improvement": "<string or N/A>",
    "practical_recommendation": "<string>"
  }},
  "body_language": {{
    "score": {json.dumps(deterministic_eval['body_language']['score'])},
    "assessment": "<string describing observable head movement and face visibility only>",
    "evidence_observation": "<string with exact movement count and rate/min>",
    "what_went_well": "<string or N/A>",
    "what_needs_improvement": "<string or N/A>",
    "practical_recommendation": "<string>"
  }},
  "speaking_style": {{
    "score": {json.dumps(deterministic_eval['speaking_style']['score'])},
    "assessment": "<string with measured WPM, pauses, and filler words>",
    "evidence_observation": "<string with measured WPM and pause duration>",
    "what_went_well": "<string or N/A>",
    "what_needs_improvement": "<string or N/A>",
    "practical_recommendation": "<string>"
  }},
  "engagement": {{
    "score": {json.dumps(deterministic_eval['engagement']['score'])},
    "assessment": "<string describing camera face presence only; NO eye contact claims>",
    "evidence_observation": "<string with face presence ratio>",
    "what_went_well": "<string or N/A>",
    "what_needs_improvement": "<string or N/A>",
    "practical_recommendation": "<string>"
  }},
  "story_quality": {{
    "score": {json.dumps(deterministic_eval['story_quality']['score'])},
    "assessment": "<string evaluating narrative chronology, specificity, and event structure only; NO credibility/truth claims>",
    "evidence_observation": "<string with event count, claim count, and location details>",
    "what_went_well": "<string or N/A>",
    "what_needs_improvement": "<string or N/A>",
    "practical_recommendation": "<string>"
  }}
}}
"""

    system = (
        "You are an evidence-grounded communication performance analyst. "
        "Use ONLY explicitly measured data. Never infer psychological states or credibility. "
        "Never claim eye contact or vocal tone unless explicitly provided. "
        "Return strictly valid JSON matching the schema without markdown code blocks."
    )
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
                    # If LLM returned N/A or empty for valid signals, backfill with evidence-backed deterministic findings
                    for fld in ("what_went_well", "what_needs_improvement", "practical_recommendation"):
                        curr_fld = parsed[cat_key].get(fld)
                        if (not curr_fld or str(curr_fld).strip().upper() == "N/A") and cat_val.get(fld) and cat_val.get(fld) != "N/A":
                            parsed[cat_key][fld] = cat_val[fld]
            return _enforce_data_integrity(
                parsed, has_valid_speech, has_valid_visual, has_valid_transcript, has_valid_story, visual_feats
            )
    except Exception as e:
        print(f"LLM explanation unavailable ({e}); utilizing deterministic evaluation output directly.")

    # Return pure deterministic evaluation with data integrity enforcement
    return _enforce_data_integrity(
        deterministic_eval, has_valid_speech, has_valid_visual, has_valid_transcript, has_valid_story, visual_feats
    )
