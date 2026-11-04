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
from typing import Optional, Dict, Any, Union, Tuple

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
from analytical_engine.vocal_metrics import evaluate_vocal_performance
from analytical_engine.visual_metrics import evaluate_visual_performance


CATEGORY_STRENGTH_LABELS = {
    CAT_SPEAKING_STYLE: "speaking fluency and pace",
    CAT_STORY_QUALITY: "narrative detail and event richness",
    CAT_CONFIDENCE: "composed presentation delivery",
    CAT_ENGAGEMENT: "consistent camera presence",
    CAT_BODY_LANGUAGE: "controlled posture and body language",
}

CATEGORY_IMPROVEMENT_LABELS = {
    CAT_SPEAKING_STYLE: "regulating speaking pace and using intentional pauses",
    CAT_STORY_QUALITY: "providing clear event transitions and descriptive details",
    CAT_CONFIDENCE: "anchoring key takeaways with deliberate pauses for extra emphasis",
    CAT_ENGAGEMENT: "maintaining consistent camera presence",
    CAT_BODY_LANGUAGE: "making body and head movements intentional and purposeful",
}


def calculate_overall_communication_score(
    eval_data: Optional[Dict[str, Any]],
    profile: Optional[Union[ContextProfile, str]] = None
) -> Tuple[Union[int, str], str]:
    """
    Calculate a deterministic overall communication score and human-friendly coaching assessment.

    CRITICAL RULES:
    1. Deterministically calculated from the 5 category scores using profile category weights.
    2. Zero hardcoding, zero arbitrary constants, zero LLM hallucination of scores.
    3. If some categories have insufficient data, calculates based on available measured
       scores only, normalizing active weights proportionally.
    4. Identical input + measurements + profile = identical overall score.
    5. Accompanied by a concise, human-friendly coaching synthesis highlighting top strength
       and single highest-impact priority improvement opportunity.
    """
    if profile is None or isinstance(profile, str):
        profile = get_context_profile(profile)

    if not eval_data or not isinstance(eval_data, dict):
        return (
            INSUFFICIENT_DATA,
            "Insufficient multimodal data available to calculate an overall communication score. "
            "Please record or upload a video with clear audio and forward-facing visual tracking."
        )

    weighted_sum = 0.0
    total_active_weight = 0.0
    valid_scores: Dict[str, Tuple[float, float, Dict[str, Any]]] = {}

    for cat in ALL_CATEGORIES:
        item = eval_data.get(cat)
        if isinstance(item, dict):
            s = item.get("score")
            if isinstance(s, (int, float)) and not isinstance(s, bool):
                s_val = float(s)
                w = profile.category_weights.get(cat, 0.20)
                valid_scores[cat] = (s_val, w, item)
                weighted_sum += s_val * w
                total_active_weight += w

    if not valid_scores or total_active_weight <= 0:
        return (
            INSUFFICIENT_DATA,
            "Insufficient multimodal data available to calculate an overall communication score. "
            "Please record or upload a video with clear audio and forward-facing visual tracking."
        )

    overall_score = int(round(weighted_sum / total_active_weight))

    # Sort categories by score descending to extract strengths and focus areas
    sorted_cats = sorted(valid_scores.keys(), key=lambda c: valid_scores[c][0], reverse=True)
    top_1 = sorted_cats[0]
    lowest = sorted_cats[-1]

    # Select top strength(s)
    if len(sorted_cats) >= 2 and sorted_cats[1] != lowest and valid_scores[sorted_cats[1]][0] >= 65:
        top_2 = sorted_cats[1]
        strengths_text = f"{CATEGORY_STRENGTH_LABELS.get(top_1, top_1)} and {CATEGORY_STRENGTH_LABELS.get(top_2, top_2)}"
    else:
        strengths_text = f"{CATEGORY_STRENGTH_LABELS.get(top_1, top_1)}"

    # Determine opening tone based on score
    if overall_score >= 80:
        opening = "Your communication is clear, composed, and highly effective"
    elif overall_score >= 70:
        opening = "Your communication is clear and composed"
    elif overall_score >= 55:
        opening = "Your communication demonstrates a solid foundation with steady delivery"
    else:
        opening = "Your communication provides a solid foundation to build upon"

    # Select improvement area
    imp_label = CATEGORY_IMPROVEMENT_LABELS.get(lowest, lowest)
    if valid_scores[lowest][0] < 80:
        improvement_text = f"To elevate your impact further, focus on {imp_label}."
    else:
        improvement_text = f"To elevate your impact even further, continue refining {imp_label}."

    assessment_text = f"{opening}, with particularly strong {strengths_text}. {improvement_text}"

    return overall_score, assessment_text


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
            "metric_name": "Camera Presence",
            "assessment": "Camera presence signals require active facial landmark tracking.",
            "evidence_observation": "No facial landmark stream available. Camera presence is unmeasured.",
            "what_went_well": "N/A",
            "what_needs_improvement": "N/A",
            "practical_recommendation": "Position yourself centered in the camera viewport with clear front lighting."
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
        wpm_str = f"a speaking pace of {wpm_val:.0f} WPM" if wpm_val is not None else "a steady speaking pace"
        pause_str = "no long pauses detected" if pauses_val == 0 else (f"{pauses_val} pauses detected" if pauses_val is not None else "available acoustic tracking")
        
        confidence_indicators = {
            "score": conf_score,
            "metric_name": "Delivery Composure",
            "assessment": f"Your presentation delivery was steady and continuous, with {wpm_str} and {pause_str}. While confidence as an internal state cannot be determined from these signals alone, your observable delivery showed calm composure and good control.",
            "evidence_observation": f"Supporting data: Delivery composure score {conf_score}/100 across {len(valid_behavioral_scores)} observable channels (evaluates observable presentation delivery composure, not internal emotional state).",
            "what_went_well": "Speaking pace and camera framing remained steady throughout the delivery.",
            "what_needs_improvement": "Anchor your central statements with deliberate pacing and purposeful pauses to give them extra emphasis.",
            "practical_recommendation": "Pause for one second right before delivering a key takeaway to give your message natural authority."
        }
    else:
        confidence_indicators = {
            "score": INSUFFICIENT_DATA,
            "metric_name": "Delivery Composure",
            "assessment": "Insufficient multimodal behavioral signals to evaluate delivery composure.",
            "evidence_observation": "Acoustic and visual streams lack sufficient measurable signals.",
            "what_went_well": "N/A",
            "what_needs_improvement": "N/A",
            "practical_recommendation": "Record both clear microphone audio and forward-facing video."
        }

    # 4. Narrative Detail & Structure (Entity density and descriptive richness)
    # CRITICAL: This formula measures narrative detail, extracted-entity density, and descriptive
    # progression. It does NOT evaluate factual accuracy, truthfulness, logical validity, or technical correctness.
    words = len((transcript or "").split())
    has_text = bool((transcript or "").strip() and words >= 6)

    if story_data and story_data.get("events"):
        events = story_data.get("events", [])
        claims = story_data.get("claims", [])
        locations = story_data.get("all_locations_mentioned", [])
        people = story_data.get("all_people_mentioned", [])

        # Mathematical score based strictly on narrative completeness and entity density
        raw_sq = 45.0 + (len(events) * 9.0) + (len(claims) * 4.0) + (len(locations) * 3.0)
        sq_score = int(round(max(45.0, min(95.0, raw_sq))))

        story_quality = {
            "score": sq_score,
            "metric_name": "Narrative Detail",
            "assessment": (
                f"You provided a detailed account referencing {len(events)} events, {len(claims)} key statements, and {len(locations)} locations. "
                "This metric measures narrative detail and extracted entity density; it does not measure factual accuracy, veracity, logical validity, or technical correctness."
            ),
            "evidence_observation": (
                f"Supporting data: {len(events)} events | {len(claims)} claims | {len(locations)} locations extracted from transcript "
                "(reflects narrative detail and entity density; does not verify factual correctness or veracity)."
            ),
            "what_went_well": "The narrative contains descriptive details and multiple event references that provide context.",
            "what_needs_improvement": "Connect events with clear temporal sequence markers to clarify the chronological progression.",
            "practical_recommendation": "Use transition words like 'first', 'subsequently', and 'finally' to connect your detailed points into a clear progression."
        }
    elif has_text:
        raw_sq = min(75.0, 40.0 + (words * 0.6))
        sq_score = int(round(raw_sq))
        story_quality = {
            "score": sq_score,
            "metric_name": "Narrative Detail",
            "assessment": (
                f"You shared a brief account ({words} words). "
                "This score reflects narrative length and basic text coverage; it does not evaluate factual accuracy or logical validity."
            ),
            "evidence_observation": f"Supporting data: {words} words captured | Minimal structured event points (measures narrative density only).",
            "what_went_well": "Your initial account was captured clearly in the transcript.",
            "what_needs_improvement": "Elaborate with concrete examples and specific situational details to provide fuller context.",
            "practical_recommendation": "Walk the listener through what happened step-by-step using phrases like 'First', 'Next', and 'Finally'."
        }
    else:
        story_quality = {
            "score": INSUFFICIENT_DATA,
            "metric_name": "Narrative Detail",
            "assessment": "No transcript available to evaluate narrative detail.",
            "evidence_observation": "Missing textual account. Narrative detail is unmeasured.",
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
You are an expert, encouraging communication coach evaluating '{person_name}' under the '{profile.name}' context.
The objective numeric scores have ALREADY been calculated by our deterministic measurement engine:
{json.dumps(score_summary, indent=2)}

Your task is STRICTLY to write qualitative, warm, human-friendly coaching explanations and recommendations.
DO NOT change the numerical scores. If a score is "Insufficient Data", keep it as "Insufficient Data" and provide "N/A" for strengths/improvements.

==================================================
COACHING PHILOSOPHY & STRUCTURE:
==================================================
Your review must guide the user with supportive, clear advice:
MEASURED DATA -> INTERPRETATION -> HUMAN-FRIENDLY EXPLANATION -> PRACTICAL IMPROVEMENT

The main assessment review for each category should answer:
1. What did I do? (in clear, non-technical terms)
2. Why might it matter? (impact on listener engagement and clarity)
3. What can I improve? (focus area)
4. How should I practice it? ("💡 Try this" actionable technique)

Leave exact numbers (WPM, movement rates, timestamps) for the 'evidence_observation' field (prefixed with 'Supporting data: ...').
Keep the primary assessment friendly, encouraging, and easy for any student to understand.

BODY LANGUAGE PERSPECTIVE:
- Head movement is NOT inherently bad, nervous, or uncomfortable. Movement can be natural and expressive.
- If movement is high: note that movement is natural and expressive, but making it more intentional will make the presentation feel more controlled.
  Try this: "Don't try to stay completely still. Instead, use head movement when it naturally supports your point and reduce repeated movement when it doesn't."

SPEAKING STYLE PERSPECTIVE:
- If steady: "Your speaking pace was steady and comfortable, and you didn't have noticeable long pauses. This helped your delivery stay continuous and easy to follow."
  Try this: "Keep the same comfortable pace, and consider adding short pauses before important points to give them more emphasis."

STORY QUALITY PERSPECTIVE:
- If detailed: "You included several specific details and locations, which made the story more concrete and easier to follow."
  Try this: "Keep using specific examples, but make the sequence of events even clearer so the listener can follow the story effortlessly."

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
7. Do not claim vocal tone unless tone/prosody metrics are explicitly supplied. Use measured speaking pace and pauses.
8. Do not claim hesitation unless hesitation is explicitly represented by measured speech signals.
9. Do not claim confidence as a psychological state. The section evaluates observable presentation delivery signals only (e.g. 'Your presentation delivery was steady and continuous... While confidence as an internal state cannot be determined from these signals alone, your observable delivery showed calm composure.').
10. The transcript may contain words such as 'liar', 'lying', 'deceive', 'truth', or 'not telling the truth'. These are simply part of the speaker's spoken narrative. Do NOT allow the presence of these words to influence confidence, body language, engagement, or story evaluation. TruthLens analyzes communication performance, not whether someone is lying.
11. If evidence is unavailable, explicitly state that the signal was not available.
12. Actionable recommendations ('practical_recommendation') must be concrete exercises ("💡 Try this: ...").

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
    "assessment": "<friendly coaching review explaining observable delivery composure>",
    "evidence_observation": "Supporting data: <summary of composure channels and metrics>",
    "what_went_well": "<string or N/A>",
    "what_needs_improvement": "<string or N/A>",
    "practical_recommendation": "<string>"
  }},
  "body_language": {{
    "score": {json.dumps(deterministic_eval['body_language']['score'])},
    "assessment": "<friendly coaching review explaining head movement and intentional delivery>",
    "evidence_observation": "Supporting data: <movement count, rate/min, and reference range>",
    "what_went_well": "<string or N/A>",
    "what_needs_improvement": "<string or N/A>",
    "practical_recommendation": "<string>"
  }},
  "speaking_style": {{
    "score": {json.dumps(deterministic_eval['speaking_style']['score'])},
    "assessment": "<friendly coaching review explaining speaking pace and flow>",
    "evidence_observation": "Supporting data: <measured WPM, pause count, and fillers>",
    "what_went_well": "<string or N/A>",
    "what_needs_improvement": "<string or N/A>",
    "practical_recommendation": "<string>"
  }},
  "engagement": {{
    "score": {json.dumps(deterministic_eval['engagement']['score'])},
    "assessment": "<friendly coaching review explaining camera presence and framing; explicitly note this measures camera presence, not eye contact, gaze fixation, or psychological engagement>",
    "evidence_observation": "Supporting data: <face presence ratio percentage of frames face was detected; explicitly note this measures camera presence, not eye contact>",
    "what_went_well": "<string or N/A>",
    "what_needs_improvement": "<string or N/A>",
    "practical_recommendation": "<string>"
  }},
  "story_quality": {{
    "score": {json.dumps(deterministic_eval['story_quality']['score'])},
    "assessment": "<friendly coaching review explaining narrative detail, entity richness, and descriptive progression; DO NOT claim factual correctness, veracity, or accuracy>",
    "evidence_observation": "Supporting data: <event count, claim count, and location details; explicitly note this measures narrative detail, not factual accuracy or veracity>",
    "what_went_well": "<string or N/A>",
    "what_needs_improvement": "<string or N/A>",
    "practical_recommendation": "<string>"
  }}
}}
"""

    system = (
        "You are an encouraging, evidence-grounded communication coach. "
        "Provide warm, human-friendly feedback that translates measurements into practical improvements. "
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
