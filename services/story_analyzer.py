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


def evaluate_individual_account(person_name: str, transcript: str, story_data: dict, speech_feats: dict, visual_feats: dict) -> dict:
    prompt = f"""
You are an expert communication analyst. Evaluate the provided communication data for '{person_name}'.
You must output a STRICT JSON object representing your assessment.
DO NOT invent evidence. Base your score ONLY on the provided JSON features.
If a data source is missing (e.g. transcript is empty, or visual tracking failed), you MUST NOT guess. Set the score to "Insufficient Data" and explain why.
For Body Language, output human-readable observations for posture, hand/body movement, facial expression, and distracting movements based on the visual metrics.
For Engagement, output an assessment of camera attention, eye-contact consistency, and natural delivery based on the visual/speech metrics.

DATA AVAILABLE:
- Transcript: {transcript if transcript else 'MISSING'}
- Story Extracted: {json.dumps(story_data) if story_data else 'MISSING'}
- Speech Features: {json.dumps(speech_feats) if speech_feats else 'MISSING'}
- Visual Features: {json.dumps(visual_feats) if visual_feats else 'MISSING'}

OUTPUT FORMAT (Valid JSON only):
{{
  "confidence_indicators": {{
    "score": <int 0-100 or "Insufficient Data">,
    "assessment": "<overall assessment of confidence indicators, NOT psychological certainty>",
    "evidence_observation": "<specific metrics/observations>",
    "what_went_well": "<strengths>",
    "what_needs_improvement": "<weaknesses>",
    "practical_recommendation": "<actionable advice>"
  }},
  "body_language": {{
    "score": <int 0-100 or "Insufficient Data">,
    "assessment": "<human-readable observations of posture, hand/body movement, facial expression, repetitive/distracting movements>",
    "evidence_observation": "<specific visual metrics>",
    "what_went_well": "<strengths>",
    "what_needs_improvement": "<weaknesses>",
    "practical_recommendation": "<actionable advice>"
  }},
  "speaking_style": {{
    "score": <int 0-100 or "Insufficient Data">,
    "assessment": "<assessment of pace, clarity, filler words, pauses>",
    "evidence_observation": "<specific speech metrics>",
    "what_went_well": "<strengths>",
    "what_needs_improvement": "<weaknesses>",
    "practical_recommendation": "<actionable advice>"
  }},
  "engagement": {{
    "score": <int 0-100 or "Insufficient Data">,
    "assessment": "<assessment of camera attention, eye-contact consistency, facial expressiveness, natural delivery>",
    "evidence_observation": "<specific visual and speech metrics>",
    "what_went_well": "<strengths>",
    "what_needs_improvement": "<weaknesses>",
    "practical_recommendation": "<actionable advice>"
  }},
  "story_quality": {{
    "score": <int 0-100 or "Insufficient Data">,
    "assessment": "<assessment of narrative clarity, evidence coverage, completeness>",
    "evidence_observation": "<specific extracted facts>",
    "what_went_well": "<strengths>",
    "what_needs_improvement": "<weaknesses>",
    "practical_recommendation": "<actionable advice>"
  }}
}}
"""
    
    system = "You are a communication analyst. Return strictly valid JSON matching the schema. No markdown wrapping."
    from services.llm_provider import call_llm
    try:
        response = call_llm(prompt=prompt, system_prompt=system)
        parsed = _parse_json_response(response, person_name)
        if parsed and all(k in parsed for k in ("confidence_indicators", "body_language", "speaking_style", "engagement", "story_quality")):
            return parsed
    except Exception as e:
        print(f"LLM Evaluation unavailable or failed ({e}), using evidence-based evaluation engine.")

    # Evidence-based deterministic evaluation fallback
    return _deterministic_evaluation(person_name, transcript, story_data, speech_feats, visual_feats)


def _deterministic_evaluation(
    person_name: str,
    transcript: str,
    story_data: Optional[dict],
    speech_feats: Optional[dict],
    visual_feats: Optional[dict]
) -> dict:
    has_text = bool((transcript or "").strip())
    has_speech = bool(speech_feats and speech_feats.get("duration_seconds", 0) > 0)
    has_visual = bool(visual_feats and visual_feats.get("tracking_reliability") != "analysis_error")
    face_detected = bool(has_visual and visual_feats.get("face_detected"))

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
    elif has_speech:
        speaking_style = {
            "score": "Insufficient Data",
            "assessment": "Audio signal contained very low amplitude or no measurable vocal speech.",
            "evidence_observation": f"Duration: {speech_feats.get('duration_seconds', 0):.1f}s, words detected: {speech_feats.get('word_count', 0)}.",
            "what_went_well": "Audio channel was successfully recorded.",
            "what_needs_improvement": "Microphone volume was insufficient for acoustic cadence evaluation.",
            "practical_recommendation": "Verify microphone input volume and speak clearly toward the microphone."
        }
    else:
        speaking_style = {
            "score": "Insufficient Data",
            "assessment": "No speech audio available for acoustic evaluation.",
            "evidence_observation": "Acoustic audio stream not provided.",
            "what_went_well": "N/A",
            "what_needs_improvement": "Provide microphone audio recording.",
            "practical_recommendation": "Record or upload an audio/video file with audible narration."
        }

    # 2. Body Language & Posture
    if has_visual and face_detected:
        hm = visual_feats.get("head_movement_count", 0)
        blinks = visual_feats.get("blink_count", 0)
        face_ratio = visual_feats.get("face_presence_ratio", 1.0)

        bl_score = 80
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
        body_language = {
            "score": bl_score,
            "assessment": f"Facial landmarks remained visible ({face_ratio:.0%} presence). Head posture was {posture_eval}.",
            "evidence_observation": f"Face presence: {face_ratio:.0%} | Head movement shifts: {hm} | Blinks: {blinks}",
            "what_went_well": "Maintained composed posture and consistent alignment within the camera frame.",
            "what_needs_improvement": "Keep head posture centered and steady when delivering primary statements." if hm > 8 else "Relax shoulder tension to project natural comfort.",
            "practical_recommendation": "Position camera at eye level approximately an arm's length away."
        }
    else:
        body_language = {
            "score": "Insufficient Data",
            "assessment": "No face or posture landmarks detected in the video frames.",
            "evidence_observation": "Visual tracking returned 0 valid face frames.",
            "what_went_well": "Video stream was initialized.",
            "what_needs_improvement": "Camera angle or lighting prevented reliable facial landmark detection.",
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
            "what_needs_improvement": "Enable camera input to measure camera presence and engagement.",
            "practical_recommendation": "Position yourself centered in the camera viewport."
        }

    # 4. Confidence Indicators
    valid_scores = []
    if isinstance(speaking_style.get("score"), int): valid_scores.append(speaking_style["score"])
    if isinstance(body_language.get("score"), int): valid_scores.append(body_language["score"])
    if isinstance(engagement.get("score"), int): valid_scores.append(engagement["score"])

    if valid_scores:
        conf_score = int(sum(valid_scores) / len(valid_scores))
        confidence_indicators = {
            "score": conf_score,
            "assessment": f"Observable behavioral signals reflect steady delivery composure across {len(valid_scores)} analyzed modalities.",
            "evidence_observation": f"Calculated across {len(valid_scores)} observable behavioral channels (mean rating: {conf_score}/100).",
            "what_went_well": "Consistent behavioral presence across observable channels.",
            "what_needs_improvement": "Harmonize vocal emphasis with facial expressiveness for key narrative points.",
            "practical_recommendation": "Anchor key statements with direct eye contact and deliberate vocal cadence."
        }
    else:
        confidence_indicators = {
            "score": "Insufficient Data",
            "assessment": "Insufficient multimodal signals to compute an evidence-backed confidence score.",
            "evidence_observation": "Acoustic and visual streams lack sufficient measurable signals.",
            "what_went_well": "Session recorded.",
            "what_needs_improvement": "Ensure both microphone and camera streams capture clear input.",
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
            "what_needs_improvement": "Specify explicit time durations and dates for each sequence.",
            "practical_recommendation": "State exact times and sequential connectors (first, then, afterward)."
        }
    elif has_text and len(transcript.split()) >= 6:
        words = len(transcript.split())
        story_quality = {
            "score": 65,
            "assessment": f"Transcript with {words} words captured. Structured narrative points are minimal.",
            "evidence_observation": f"Raw transcript contains {words} words.",
            "what_went_well": "Account was successfully captured in text.",
            "what_needs_improvement": "Add specific time markers and chronological sequence points.",
            "practical_recommendation": "Structure the narrative with specific timestamps and locations."
        }
    else:
        story_quality = {
            "score": "Insufficient Data",
            "assessment": "No transcript available to evaluate narrative structure.",
            "evidence_observation": "Missing textual account.",
            "what_went_well": "N/A",
            "what_needs_improvement": "Provide a spoken or manual narrative account.",
            "practical_recommendation": "Speak clearly into the microphone or enter a transcript manually."
        }

    return {
        "confidence_indicators": confidence_indicators,
        "body_language": body_language,
        "speaking_style": speaking_style,
        "engagement": engagement,
        "story_quality": story_quality
    }
