"""
services/story_analyzer.py
─────────────────────────────────────────────────────────────────────────────
TruthLens AI — Stage 3: AI story understanding and structured fact extraction.

Given a plain-text story transcript, this module uses an LLM to extract
structured facts — people, locations, times, activities, and event sequences —
without inventing information that is not present in the transcript.

Public API
──────────
  extract_story_facts(transcript, person_name)  → dict
  validate_extracted_story(data)                → tuple[bool, list[str]]

Design decisions
────────────────
  • Temperature is always 0.0 (set in llm_provider.py) to minimise
    creative hallucination.
  • The prompt explicitly forbids the model from inventing facts.
  • Fields that are not mentioned in the transcript must be null / [].
  • The response is expected to be pure JSON; this module robustly strips
    markdown code fences before parsing.
"""

from __future__ import annotations

import json
import re
from typing import Any

from services.llm_provider import call_llm


# ── Prompt templates ───────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """
You are a precise information-extraction assistant for TruthLens AI.

Your ONLY job is to extract facts that are EXPLICITLY stated in the transcript.

STRICT RULES:
1. Do NOT invent, assume, or infer any information not present in the text.
2. Do NOT add times, dates, locations, or people that were not mentioned.
3. Use null for any string field where the information is missing.
4. Use an empty list [] for any list field where no items were mentioned.
5. Return ONLY a single valid JSON object — no explanation, no markdown fences,
   no extra text before or after the JSON.
6. Your response must be parseable by Python's json.loads() without modification.
""".strip()

_USER_PROMPT_TEMPLATE = """
Extract structured facts from the following story transcript.

Person Name: {person_name}

Transcript:
\"\"\"
{transcript}
\"\"\"

Return a JSON object that exactly follows this schema:

{{
  "person": "<person_name as provided>",
  "summary": "<one-sentence summary of what happened — only from the text>",
  "events": [
    {{
      "event_id": "<string, e.g., E1, E2>",
      "sequence": <integer, narrative order starting from 1>,
      "time": "<when it occurred exactly as stated, or null>",
      "time_normalized": "<normalized time if possible, or null>",
      "location": "<where it happened — or null>",
      "people": ["<names of people present — empty list if none>"],
      "action": "<what the person was doing — or null>",
      "description": "<brief description of the event>",
      "source_text": "<the original sentence from the transcript>"
    }}
  ],
  "claims": [
    {{
      "claim_id": "<string, e.g., C1, C2>",
      "subject": "<what the claim is about, e.g., conversation with Rahul>",
      "attribute": "<specific attribute, e.g., duration>",
      "value": "<the claimed value, e.g., about 10 minutes>",
      "source_text": "<the original sentence from the transcript>"
    }}
  ],
  "all_people_mentioned": ["<every person name in the transcript>"],
  "all_locations_mentioned": ["<every location in the transcript>"],
  "all_times_mentioned": ["<every time reference in the transcript>"],
  "all_dates_mentioned": ["<every date reference in the transcript>"],
  "extraction_confidence": "<high | medium | low — based on how clear the transcript is>"
}}

Remember: only include facts that appear in the transcript. Do NOT invent missing values.
""".strip()


# ── Public functions ───────────────────────────────────────────────────────────

def extract_story_facts(transcript: str, person_name: str) -> dict[str, Any]:
    """
    Use an LLM to extract structured facts from a spoken-story transcript.

    Parameters
    ----------
    transcript : str
        The raw text transcript of the person's story.
    person_name : str
        A label such as "Person A" used to populate the 'person' field.

    Returns
    -------
    dict
        A dictionary matching the extraction schema defined in the prompt.

    Raises
    ------
    ValueError
        If the transcript is empty.
    RuntimeError
        If the LLM call fails or the response cannot be parsed as JSON.
    """
    if not transcript or not transcript.strip():
        raise ValueError("Transcript is empty. Record and transcribe a story first.")

    prompt = _USER_PROMPT_TEMPLATE.format(
        person_name=person_name,
        transcript=transcript.strip(),
    )

    try:
        raw_response = call_llm(prompt=prompt, system_prompt=_SYSTEM_PROMPT)
        parsed = _parse_json_response(raw_response, person_name)
        is_valid, _ = validate_extracted_story(parsed)
        if is_valid:
            return parsed
    except Exception as e:
        print(f"LLM story extraction unavailable or failed ({e}), using evidence-based heuristic story extractor.")

    return _deterministic_story_extraction(transcript, person_name)


def _deterministic_story_extraction(transcript: str, person_name: str = "Person") -> dict[str, Any]:
    """
    Deterministic rule-based fact extraction when LLM is unavailable or offline.
    Extracts events, claims, times, locations, and people directly from sentences.
    """
    raw_sentences = [s.strip() for s in re.split(r'[.!?]+', transcript) if s.strip()]
    if not raw_sentences:
        raw_sentences = [transcript.strip()]
        
    events = []
    claims = []
    all_times = set()
    all_locations = set()
    all_people = set()
    
    location_keywords = ["library", "campus", "cafe", "dining hall", "room", "office", "home", "building", "park", "store", "station", "house", "table"]
    time_regex = re.compile(r'\b(?:\d{1,2}(?::\d{2})?\s*(?:am|pm|AM|PM)|\d+\s*(?:hour|minute|day|week)s?|morning|afternoon|evening|yesterday|today)\b', re.IGNORECASE)
    
    for i, s in enumerate(raw_sentences, start=1):
        t_match = time_regex.findall(s)
        time_found = ", ".join(t_match) if t_match else None
        if t_match:
            for t in t_match:
                all_times.add(t)
            
        loc_found = None
        for loc in location_keywords:
            if re.search(r'\b' + re.escape(loc) + r'\b', s, re.IGNORECASE):
                loc_found = loc
                all_locations.add(loc)
                break
                
        people_found = []
        words = re.findall(r'\b[A-Z][a-z]+\b', s)
        for w in words:
            if w.lower() not in {"i", "after", "then", "afterward", "when", "at", "the", "he", "she", "we", "they", "my", "so", "did", "person"}:
                people_found.append(w)
                all_people.add(w)
                
        events.append({
            "event_id": f"E{i}",
            "sequence": i,
            "description": s,
            "time": time_found,
            "time_normalized": time_found,
            "time_or_relative_time": time_found,
            "location": loc_found,
            "people": people_found if people_found else None,
            "source_text": s,
        })
        
        claims.append({
            "claim_id": f"C{i}",
            "subject": person_name,
            "attribute": "statement",
            "value": s,
            "source_text": s,
        })
        
    summary = raw_sentences[0] if len(raw_sentences) == 1 else f"{person_name}'s statement covering {len(raw_sentences)} key events."
    
    return {
        "person": person_name,
        "summary": summary,
        "extraction_confidence": "medium",
        "events": events,
        "claims": claims,
        "all_people_mentioned": sorted(list(all_people)),
        "all_locations_mentioned": sorted(list(all_locations)),
        "all_times_mentioned": sorted(list(all_times)),
        "all_dates_mentioned": [],
        "is_fallback": True,
    }



def validate_extracted_story(data: Any) -> tuple[bool, list[str]]:
    """
    Validate that the extracted story dictionary contains the expected fields.

    Parameters
    ----------
    data : Any
        The object returned by extract_story_facts().

    Returns
    -------
    tuple[bool, list[str]]
        (True, []) if the data is valid.
        (False, [error messages]) if validation fails.
    """
    errors: list[str] = []

    if not isinstance(data, dict):
        return False, ["Extracted result is not a dictionary."]

    # Required top-level string fields
    for field in ("person", "summary", "extraction_confidence"):
        if field not in data:
            errors.append(f"Missing required field: '{field}'.")
        elif not isinstance(data[field], (str, type(None))):
            errors.append(f"Field '{field}' must be a string or null.")

    # Required list fields
    for field in (
        "events",
        "claims",
        "all_people_mentioned",
        "all_locations_mentioned",
        "all_times_mentioned",
        "all_dates_mentioned",
    ):
        if field not in data:
            errors.append(f"Missing required field: '{field}'.")
        elif not isinstance(data[field], list):
            errors.append(f"Field '{field}' must be a list.")

    # Validate each event object
    if isinstance(data.get("events"), list):
        for i, event in enumerate(data["events"], start=1):
            if not isinstance(event, dict):
                errors.append(f"Event {i} is not a dictionary.")
                continue
            
            for req in ("event_id", "sequence", "description", "source_text"):
                if req not in event:
                    errors.append(f"Event {i} is missing required field: '{req}'.")
            
            if "people" in event and not isinstance(event.get("people"), (list, type(None))):
                errors.append(f"Event {i}: 'people' must be a list or null.")
                
    # Validate each claim object
    if isinstance(data.get("claims"), list):
        for i, claim in enumerate(data["claims"], start=1):
            if not isinstance(claim, dict):
                errors.append(f"Claim {i} is not a dictionary.")
                continue
            
            for req in ("claim_id", "subject", "attribute", "value", "source_text"):
                if req not in claim:
                    errors.append(f"Claim {i} is missing required field: '{req}'.")

    return len(errors) == 0, errors


# ── Internal helpers ───────────────────────────────────────────────────────────

def _parse_json_response(raw: str, person_name: str) -> dict[str, Any]:
    """
    Parse a JSON object from the LLM's raw text response.

    LLMs sometimes wrap their JSON output in markdown code fences
    (```json … ```).  This function strips those fences before parsing.

    Raises RuntimeError with a helpful message if parsing fails.
    """
    # Strip leading / trailing whitespace
    text = raw.strip()

    # Remove markdown code fences if present: ```json ... ``` or ``` ... ```
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text)
    text = text.strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"The LLM returned a response that could not be parsed as JSON.\n"
            f"Parse error: {exc}\n"
            f"Raw response (first 500 chars):\n{raw[:500]}"
        ) from exc

    if not isinstance(data, dict):
        raise RuntimeError(
            f"Expected a JSON object from the LLM, but got: {type(data).__name__}."
        )

    # Safety net: ensure person field always matches the label we passed in
    data.setdefault("person", person_name)

    return data

# ── Individual Assessment ───────────────────────────────────────────────────────


def evaluate_individual_account(
    person_name: str,
    transcript: str,
    story_data: Optional[dict],
    speech_feats: Optional[dict],
    visual_feats: Optional[dict]
) -> dict:
    has_valid_transcript = bool((transcript or "").strip() and len(transcript.split()) >= 6)
    has_valid_speech = bool(
        speech_feats 
        and speech_feats.get("duration_seconds") is not None 
        and speech_feats.get("duration_seconds") > 0 
        and speech_feats.get("speaking_rate_wpm") is not None
        and speech_feats.get("reliability_flag") == "good"
    )
    has_valid_visual = bool(
        visual_feats 
        and visual_feats.get("face_detected") is True 
        and visual_feats.get("tracking_reliability") == "good"
    )
    has_valid_story = bool(story_data and (story_data.get("events") or story_data.get("claims")))

    # Ensure head movement rate and normal range are present if visual features exist
    if visual_feats and visual_feats.get("head_movement_count") is not None:
        if visual_feats.get("head_movement_rate_per_min") is None:
            dur = visual_feats.get("duration_seconds") or (speech_feats.get("duration_seconds") if speech_feats else None)
            if dur and dur >= 3.0:
                visual_feats["head_movement_rate_per_min"] = round((visual_feats["head_movement_count"] / dur) * 60.0, 1)
        visual_feats.setdefault("head_movement_typical_range", "15-35/min")

    prompt = f"""
You are an expert communication and performance analyst evaluating '{person_name}'.
You must output a STRICT JSON object representing your assessment.
DO NOT invent evidence. Base your score ONLY on the provided JSON features.

CRITICAL RULES FOR MISSING DATA & DATA INTEGRITY:
1. Speaking Style & Fluency:
   - REQUIRES valid speech features (measured speaking rate WPM, duration, pauses).
   - If Speech Features are MISSING, null, or duration is null: you MUST set:
     "score": "Insufficient Data", "what_went_well": "N/A", "what_needs_improvement": "N/A",
     "assessment": "Audio speech features were unavailable or could not be measured.",
     "evidence_observation": "Acoustic speech stream not available or unmeasured.",
     "practical_recommendation": "Record or upload an audio track with clear audible speech."
2. Body Language & Posture:
   - REQUIRES valid visual features with face_detected=True.
   - If Visual Features are MISSING, face_detected is False, or tracking failed: you MUST set:
     "score": "Insufficient Data", "what_went_well": "N/A", "what_needs_improvement": "N/A",
     "assessment": "Visual tracking did not detect facial landmarks.",
     "evidence_observation": "No face detected in video stream.",
     "practical_recommendation": "Ensure camera is positioned at eye-level with adequate lighting."
   - If visual features ARE present: Head movement is normalized as a rate (movements per minute) with typical conversational range of 15-35 movements/min. Use this rate to make an evidence-backed assessment rather than vague hedging.
3. Engagement & Delivery:
   - REQUIRES valid visual camera tracking (face presence ratio, gaze/attention consistency).
   - If Visual Features are MISSING or face_detected is False: you MUST set:
     "score": "Insufficient Data", "what_went_well": "N/A", "what_needs_improvement": "N/A",
     "assessment": "Engagement signals require camera tracking to evaluate eye contact and visual presence.",
     "evidence_observation": "Visual landmark stream unavailable.",
     "practical_recommendation": "Maintain camera presence centered within the frame."
   - DO NOT fabricate advice like 'practice maintaining eye contact' if visual tracking was not measured!
4. Confidence Indicators:
   - Evaluates delivery conviction and assertion certainty.
   - If BOTH speech and visual features are MISSING/unmeasured: you MUST set:
     "score": "Insufficient Data", "what_went_well": "N/A", "what_needs_improvement": "N/A",
     "assessment": "Insufficient multimodal behavioral signals to evaluate delivery confidence.",
     "evidence_observation": "Acoustic and visual streams lack measurable delivery signals.",
     "practical_recommendation": "Record both clear microphone audio and forward-facing video."
   - Evaluates certainty markers, hedges (e.g., 'maybe', 'I guess'), and vocal/visual composure.
   - NEVER critique timeline gaps, dates, or narrative structure in this category.
5. Story Quality & Structure:
   - Focuses STRICTLY on narrative structure: chronological sequence, setting, character detail, and timeline coherence.
   - If Transcript is MISSING or < 6 words: you MUST set:
     "score": "Insufficient Data", "what_went_well": "N/A", "what_needs_improvement": "N/A"
   - DO NOT repeat claim-verifiability or evidence-gathering critiques here. Keep recommendations focused on narrative storytelling (chronological transition words, scene setting, timeline specificity).

CRITICAL RULE FOR CATEGORY INDEPENDENCE:
Confidence Indicators and Story Quality & Structure MUST evaluate separate signals. Confidence Indicators focuses on conviction and assertions; Story Quality focuses on chronological narrative flow. They must NEVER generate duplicate or near-identical improvement text.

DATA AVAILABLE:
- Transcript: {transcript if transcript else 'MISSING'}
- Story Extracted: {json.dumps(story_data) if story_data else 'MISSING'}
- Speech Features: {json.dumps(speech_feats) if has_valid_speech else 'MISSING (Acoustic audio unavailable or null)'}
- Visual Features: {json.dumps(visual_feats) if has_valid_visual else 'MISSING (Camera video unavailable or no face detected)'}

OUTPUT FORMAT (Strictly Valid JSON only):
{{
  "confidence_indicators": {{
    "score": <int 0-100 or "Insufficient Data">,
    "assessment": "<string>",
    "evidence_observation": "<string>",
    "what_went_well": "<string or N/A>",
    "what_needs_improvement": "<string or N/A>",
    "practical_recommendation": "<string>"
  }},
  "body_language": {{
    "score": <int 0-100 or "Insufficient Data">,
    "assessment": "<string>",
    "evidence_observation": "<string>",
    "what_went_well": "<string or N/A>",
    "what_needs_improvement": "<string or N/A>",
    "practical_recommendation": "<string>"
  }},
  "speaking_style": {{
    "score": <int 0-100 or "Insufficient Data">,
    "assessment": "<string>",
    "evidence_observation": "<string>",
    "what_went_well": "<string or N/A>",
    "what_needs_improvement": "<string or N/A>",
    "practical_recommendation": "<string>"
  }},
  "engagement": {{
    "score": <int 0-100 or "Insufficient Data">,
    "assessment": "<string>",
    "evidence_observation": "<string>",
    "what_went_well": "<string or N/A>",
    "what_needs_improvement": "<string or N/A>",
    "practical_recommendation": "<string>"
  }},
  "story_quality": {{
    "score": <int 0-100 or "Insufficient Data">,
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
    try:
        response = call_llm(prompt=prompt, system_prompt=system)
        parsed = _parse_json_response(response, person_name)
        if parsed and all(k in parsed for k in ("confidence_indicators", "body_language", "speaking_style", "engagement", "story_quality")):
            return _enforce_data_integrity(parsed, has_valid_speech, has_valid_visual, has_valid_transcript, has_valid_story, visual_feats)
    except Exception as e:
        print(f"LLM Evaluation unavailable or failed ({e}), using evidence-based evaluation engine.")

    # Evidence-based deterministic evaluation fallback
    fallback_res = _deterministic_evaluation(person_name, transcript, story_data, speech_feats, visual_feats)
    return _enforce_data_integrity(fallback_res, has_valid_speech, has_valid_visual, has_valid_transcript, has_valid_story, visual_feats)


def _enforce_data_integrity(
    eval_data: dict,
    has_valid_speech: bool,
    has_valid_visual: bool,
    has_valid_transcript: bool,
    has_valid_story: bool,
    visual_feats: Optional[dict] = None
) -> dict:
    """
    Structurally enforce that categories with missing prerequisite signals
    cannot have hallucinated scores or advice. Also prevents duplicate advice across categories.
    """
    if not isinstance(eval_data, dict):
        eval_data = {}

    # 1. Speaking style requires valid acoustic speech
    if not has_valid_speech:
        eval_data["speaking_style"] = {
            "score": "Insufficient Data",
            "assessment": "No speech audio available or acoustic metrics could not be extracted.",
            "evidence_observation": "Acoustic audio stream not provided or extraction returned null metrics.",
            "what_went_well": "N/A",
            "what_needs_improvement": "N/A",
            "practical_recommendation": "Record or upload an audio/video file with audible narration."
        }

    # 2. Body language requires valid visual face tracking
    if not has_valid_visual:
        eval_data["body_language"] = {
            "score": "Insufficient Data",
            "assessment": "No face or posture landmarks detected in the video frames.",
            "evidence_observation": "Visual tracking returned 0 valid face frames.",
            "what_went_well": "N/A",
            "what_needs_improvement": "N/A",
            "practical_recommendation": "Ensure face is well-lit from the front and directly faces the camera."
        }
    else:
        hm_rate = visual_feats.get("head_movement_rate_per_min") if visual_feats else None
        hm_count = visual_feats.get("head_movement_count") if visual_feats else None
        if hm_rate is not None and hm_count is not None:
            bl_item = eval_data.get("body_language", {})
            obs = bl_item.get("evidence_observation", "")
            if "range" not in obs and "Head movement" not in obs:
                bl_item["evidence_observation"] = f"Head movements: {hm_count} ({hm_rate:.1f}/min, typical range: 15-35/min) | {obs}".strip(" |")

    # 3. Engagement requires camera tracking
    if not has_valid_visual:
        eval_data["engagement"] = {
            "score": "Insufficient Data",
            "assessment": "Engagement signals require active camera tracking to measure eye contact consistency.",
            "evidence_observation": "No facial landmark stream available to evaluate camera attention.",
            "what_went_well": "N/A",
            "what_needs_improvement": "N/A",
            "practical_recommendation": "Position yourself centered in the camera viewport with clear lighting."
        }

    # 4. Confidence indicators require multimodal delivery signals
    if not has_valid_speech and not has_valid_visual:
        eval_data["confidence_indicators"] = {
            "score": "Insufficient Data",
            "assessment": "Insufficient multimodal behavioral signals to evaluate delivery confidence.",
            "evidence_observation": "Acoustic and visual streams lack sufficient measurable signals.",
            "what_went_well": "N/A",
            "what_needs_improvement": "N/A",
            "practical_recommendation": "Record both clear microphone audio and forward-facing video."
        }

    # 5. Story quality requires transcript
    if not has_valid_transcript:
        eval_data["story_quality"] = {
            "score": "Insufficient Data",
            "assessment": "No transcript available to evaluate narrative structure.",
            "evidence_observation": "Missing textual account.",
            "what_went_well": "N/A",
            "what_needs_improvement": "N/A",
            "practical_recommendation": "Provide a spoken or manual narrative account."
        }

    # Check for duplicate improvement text between Confidence Indicators and Story Quality (Issue 5)
    ci = eval_data.get("confidence_indicators", {})
    sq = eval_data.get("story_quality", {})
    ci_imp = str(ci.get("what_needs_improvement", "")).strip().lower()
    sq_imp = str(sq.get("what_needs_improvement", "")).strip().lower()
    
    if ci_imp != "n/a" and sq_imp != "n/a" and (ci_imp == sq_imp or ("claim" in sq_imp and ("evidence" in sq_imp or "support" in sq_imp))):
        sq["what_needs_improvement"] = "Incorporate specific timestamps, location context, and sequential transition words to improve narrative chronology."
        sq["practical_recommendation"] = "Anchor each event with explicit time markers (e.g., 'at 2 PM', 'shortly afterward') and spatial details."

    # Ensure any category with "Insufficient Data" has "N/A" for what_went_well and what_needs_improvement
    for k, item in eval_data.items():
        if isinstance(item, dict) and item.get("score") == "Insufficient Data":
            item["what_went_well"] = "N/A"
            item["what_needs_improvement"] = "N/A"

    return eval_data


def _deterministic_evaluation(
    person_name: str,
    transcript: str,
    story_data: Optional[dict],
    speech_feats: Optional[dict],
    visual_feats: Optional[dict]
) -> dict:
    has_text = bool((transcript or "").strip() and len(transcript.split()) >= 6)
    has_speech = bool(
        speech_feats 
        and speech_feats.get("duration_seconds") is not None 
        and speech_feats.get("duration_seconds") > 0 
        and speech_feats.get("speaking_rate_wpm") is not None
        and speech_feats.get("reliability_flag") == "good"
    )
    has_visual = bool(
        visual_feats 
        and visual_feats.get("face_detected") is True 
        and visual_feats.get("tracking_reliability") == "good"
    )
    face_detected = has_visual

    # 1. Speaking Style
    if has_speech and speech_feats.get("speaking_rate_wpm", 0) > 15:
        wpm = speech_feats.get("speaking_rate_wpm", 0.0)
        pauses = speech_feats.get("pause_count", 0)
        fillers = speech_feats.get("filler_word_count", 0)
        pause_sec = speech_feats.get("total_pause_duration_sec", 0.0)

        spk_score = 80
        if 115 <= wpm <= 165:
            spk_score += 10
            cadence = "well-paced and conversational"
        elif wpm < 115:
            spk_score -= 10
            cadence = "deliberate and measured"
        else:
            spk_score -= 10
            cadence = "rapid and hurried"

        if fillers > 3:
            spk_score -= 10
        if pauses > 5:
            spk_score -= 5

        spk_score = max(45, min(95, int(spk_score)))
        speaking_style = {
            "score": spk_score,
            "assessment": f"Vocal cadence was {cadence} ({wpm:.0f} WPM) with {pauses} noticeable pauses and {fillers} filler words.",
            "evidence_observation": f"Speaking rate: {wpm:.0f} WPM | Pauses: {pauses} ({pause_sec:.1f}s) | Fillers: {fillers}",
            "what_went_well": "Consistent vocal pace with clear word articulation." if spk_score >= 75 else "Spoken narrative captured with identifiable pacing cadence.",
            "what_needs_improvement": f"Reduce filler words ({fillers} detected) and smooth sentence transitions." if fillers > 2 else "Keep pauses intentional when emphasizing important points.",
            "practical_recommendation": "Use brief silent breaths rather than vocal fillers when moving between thoughts."
        }
    else:
        speaking_style = {
            "score": "Insufficient Data",
            "assessment": "No speech audio available or acoustic metrics could not be extracted.",
            "evidence_observation": "Acoustic audio stream not provided or extraction returned null metrics.",
            "what_went_well": "N/A",
            "what_needs_improvement": "N/A",
            "practical_recommendation": "Record or upload an audio/video file with audible narration."
        }

    # 2. Body Language & Posture
    if has_visual and face_detected:
        hm = visual_feats.get("head_movement_count", 0)
        hm_rate = visual_feats.get("head_movement_rate_per_min")
        blinks = visual_feats.get("blink_count", 0)
        face_ratio = visual_feats.get("face_presence_ratio", 1.0)

        bl_score = 80
        if hm_rate is not None:
            if 15 <= hm_rate <= 35:
                bl_score += 10
                posture_eval = f"natural and conversational ({hm_rate:.1f}/min, within typical 15-35/min range)"
            elif hm_rate < 15:
                posture_eval = f"stable and composed ({hm_rate:.1f}/min, steady posture)"
            else:
                bl_score -= 10
                posture_eval = f"frequent head movement shifts ({hm_rate:.1f}/min, above typical 15-35/min range)"
        else:
            if hm <= 8:
                bl_score += 10
                posture_eval = "stable and composed"
            elif hm <= 18:
                posture_eval = "moderately dynamic with natural head tilts"
            else:
                bl_score -= 10
                posture_eval = "frequent head shifts and re-orientations"

        if face_ratio < 0.7:
            bl_score -= 15

        bl_score = max(50, min(95, int(bl_score)))
        hm_display = f"{hm} ({hm_rate:.1f}/min, normal range: 15-35/min)" if hm_rate is not None else str(hm)
        body_language = {
            "score": bl_score,
            "assessment": f"Facial landmarks remained visible ({face_ratio:.0%} presence). Head posture was {posture_eval}.",
            "evidence_observation": f"Face presence: {face_ratio:.0%} | Head movements: {hm_display} | Blinks: {blinks}",
            "what_went_well": "Maintained composed posture and consistent alignment within the camera frame.",
            "what_needs_improvement": "Keep head posture centered and steady when delivering primary statements." if (hm_rate and hm_rate > 35) or hm > 18 else "Relax shoulder tension to project natural comfort.",
            "practical_recommendation": "Position camera at eye level approximately an arm's length away."
        }
    else:
        body_language = {
            "score": "Insufficient Data",
            "assessment": "No face or posture landmarks detected in the video frames.",
            "evidence_observation": "Visual tracking returned 0 valid face frames.",
            "what_went_well": "N/A",
            "what_needs_improvement": "N/A",
            "practical_recommendation": "Ensure face is well-lit from the front and directly faces the camera."
        }

    # 3. Engagement & Camera Presence
    if has_visual and face_detected:
        face_ratio = visual_feats.get("face_presence_ratio", 1.0)
        hm = visual_feats.get("head_movement_count", 0)
        eng_score = int(face_ratio * 70 + (15 if hm <= 10 else 5) + 5)
        eng_score = max(50, min(95, eng_score))

        engagement = {
            "score": eng_score,
            "assessment": f"Direct camera presence maintained throughout {face_ratio:.0%} of the session with active responsiveness.",
            "evidence_observation": f"Face presence ratio: {face_ratio:.0%} | Landmark continuity: {visual_feats.get('tracking_reliability', 'good')}",
            "what_went_well": f"Continuous camera presence and forward-facing engagement ({face_ratio:.0%}).",
            "what_needs_improvement": "Maintain gaze on the camera lens when formulating thoughts.",
            "practical_recommendation": "Look directly at the webcam lens rather than your own preview window."
        }
    else:
        engagement = {
            "score": "Insufficient Data",
            "assessment": "Engagement signals require active facial landmark tracking.",
            "evidence_observation": "No facial landmark stream available.",
            "what_went_well": "N/A",
            "what_needs_improvement": "N/A",
            "practical_recommendation": "Position yourself centered in the camera viewport."
        }

    # 4. Confidence Indicators
    valid_scores = []
    if isinstance(speaking_style.get("score"), int): valid_scores.append(speaking_style["score"])
    if isinstance(body_language.get("score"), int): valid_scores.append(body_language["score"])
    if isinstance(engagement.get("score"), int): valid_scores.append(engagement["score"])

    if valid_scores and (has_speech or has_visual):
        conf_score = int(sum(valid_scores) / len(valid_scores))
        confidence_indicators = {
            "score": conf_score,
            "assessment": f"Observable behavioral signals reflect steady delivery composure across {len(valid_scores)} analyzed modalities.",
            "evidence_observation": f"Calculated across {len(valid_scores)} observable behavioral channels (mean rating: {conf_score}/100).",
            "what_went_well": "Consistent vocal and physical presence during delivery.",
            "what_needs_improvement": "Minimize verbal hedges (e.g., 'maybe', 'I guess') and anchor key assertions with steady delivery.",
            "practical_recommendation": "Pause briefly before delivering central points to convey composure."
        }
    else:
        confidence_indicators = {
            "score": "Insufficient Data",
            "assessment": "Insufficient multimodal signals to compute an evidence-backed confidence score.",
            "evidence_observation": "Acoustic and visual streams lack sufficient measurable signals.",
            "what_went_well": "N/A",
            "what_needs_improvement": "N/A",
            "practical_recommendation": "Re-record in a quiet, well-lit environment speaking audibly."
        }

    # 5. Story Quality & Structure
    if story_data and story_data.get("events"):
        events = story_data.get("events", [])
        claims = story_data.get("claims", [])
        locations = story_data.get("all_locations_mentioned", [])
        people = story_data.get("all_people_mentioned", [])

        sq_score = min(95, 60 + len(events) * 6 + len(claims) * 4 + len(locations) * 3)
        story_quality = {
            "score": int(sq_score),
            "assessment": f"Account exhibits clear chronological structure with {len(events)} events, {len(claims)} claims, and {len(locations)} locations.",
            "evidence_observation": f"{len(events)} events, {len(claims)} claims, {len(locations)} locations, {len(people)} people referenced.",
            "what_went_well": "Clear sequential narrative with identifiable factual anchors.",
            "what_needs_improvement": "Incorporate specific timestamps, location context, and sequential transition words to improve narrative chronology.",
            "practical_recommendation": "Anchor each event with explicit time markers (e.g., 'at 2 PM', 'shortly afterward') and spatial details."
        }
    elif has_text and len(transcript.split()) >= 6:
        words = len(transcript.split())
        story_quality = {
            "score": 65,
            "assessment": f"Transcript with {words} words captured. Structured narrative points are minimal.",
            "evidence_observation": f"Raw transcript contains {words} words.",
            "what_went_well": "Account was successfully captured in text.",
            "what_needs_improvement": "Add specific time markers and chronological sequence connectors (first, then, afterward).",
            "practical_recommendation": "Structure the narrative with specific timestamps and locations."
        }
    else:
        story_quality = {
            "score": "Insufficient Data",
            "assessment": "No transcript available to evaluate narrative structure.",
            "evidence_observation": "Missing textual account.",
            "what_went_well": "N/A",
            "what_needs_improvement": "N/A",
            "practical_recommendation": "Provide a spoken or manual narrative account."
        }

    return {
        "confidence_indicators": confidence_indicators,
        "body_language": body_language,
        "speaking_style": speaking_style,
        "engagement": engagement,
        "story_quality": story_quality
    }
