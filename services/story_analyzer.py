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
    story_data: Optional[dict] = None,
    speech_feats: Optional[dict] = None,
    visual_feats: Optional[dict] = None,
    profile_key: Optional[str] = None
) -> dict:
    """
    Evaluate an individual account under the unified deterministic & context engine.
    Calculates exact evidence-backed scores, obtains qualitative explanations,
    and structurally enforces data integrity.
    """
    from analytical_engine.evaluator import evaluate_account_with_explanation
    return evaluate_account_with_explanation(
        person_name=person_name,
        transcript=transcript,
        story_data=story_data,
        speech_feats=speech_feats,
        visual_feats=visual_feats,
        profile_key=profile_key
    )



def _sanitize_assessment_text(text: str) -> str:
    """
    Sanitize text to guarantee that unmeasured signals or psychological/deception
    inferences are strictly scrubbed and replaced with grounded presentation language.
    """
    if not text or not isinstance(text, str) or text.strip().upper() == "N/A":
        return text

    # 1. Strip eye contact claims (eye contact is unmeasured; face presence != eye contact)
    text = re.sub(r"\b(?:speaker\s+)?maintains?\s+(?:strong\s+|steady\s+|good\s+|direct\s+)?eye\s*contact\b", "maintains camera face visibility", text, flags=re.IGNORECASE)
    text = re.sub(r"\b(?:strong|stable|steady|consistent|good|direct)\s+eye\s*contact(?:\s+consistency|\s+maintenance)?\b", "consistent face visibility", text, flags=re.IGNORECASE)
    text = re.sub(r"\b(?:weak|poor|lack\s+of|irregular)\s+eye\s*contact\b", "reduced face visibility", text, flags=re.IGNORECASE)
    text = re.sub(r"\beye\s*contact\b", "camera face visibility", text, flags=re.IGNORECASE)

    # 2. Strip vocal tone claims (tone/prosody is unmeasured)
    text = re.sub(r"\bconversational\s+tone\b", "conversational speaking pace", text, flags=re.IGNORECASE)
    text = re.sub(r"\b(?:tone\s+is\s+steady|steady\s+tone|consistent\s+tone)\b", "speaking pace is steady", text, flags=re.IGNORECASE)
    text = re.sub(r"\b(?:calm|measured)\s+tone\b", "measured speaking pace", text, flags=re.IGNORECASE)
    text = re.sub(r"\bvocal\s+tone\b", "speaking rate", text, flags=re.IGNORECASE)
    text = re.sub(r"\bmonotone\b", "uniform pacing", text, flags=re.IGNORECASE)

    # 3. Strip unmeasured hesitation claims
    text = re.sub(r"\bmoments\s+where\s+hesitance\s+is\s+noticeable\b", "measured pauses between statements", text, flags=re.IGNORECASE)
    text = re.sub(r"\b(?:noticeable\s+)?hesitan(?:ce|cy)\b", "pause duration", text, flags=re.IGNORECASE)
    text = re.sub(r"\bhesitant\b", "deliberate in pacing", text, flags=re.IGNORECASE)

    # 4. Strip psychological emotion/confidence claims (observable signals only)
    text = re.sub(r"\b(?:the\s+)?speaker\s+demonstrates?\s+(?:moderate|high|strong)\s+confidence\b", "The speaker maintains steady presentation delivery", text, flags=re.IGNORECASE)
    text = re.sub(r"\b(?:the\s+)?speaker\s+is\s+confident\b", "The speaker maintains a steady speaking pace", text, flags=re.IGNORECASE)
    text = re.sub(r"\b(?:the\s+)?speaker\s+(?:lacks?\s+confidence|is\s+nervous|sounds?\s+nervous|sounds?\s+uncertain)\b", "presentation delivery shows pacing variations", text, flags=re.IGNORECASE)
    text = re.sub(r"\bindicates?\s+(?:nervousness|deception|lack\s+of\s+confidence)\b", "reflects pacing or movement frequency", text, flags=re.IGNORECASE)
    text = re.sub(r"\bappears?\s+uncomfortable\b", "shows frequent movement shifts", text, flags=re.IGNORECASE)

    # 5. Strip credibility, truthfulness, and deception claims
    text = re.sub(r"\benhances?\s+the\s+credibility\s+of\s+the\s+claims(?:\s+made)?\b", "provides additional detail to the narrative", text, flags=re.IGNORECASE)
    text = re.sub(r"\bcredibility\s+of\s+the\s+claims\b", "detail of the claims", text, flags=re.IGNORECASE)
    text = re.sub(r"\b(?:enhances?|improves?)\s+(?:the\s+)?credibility\b", "improves narrative specificity", text, flags=re.IGNORECASE)
    text = re.sub(r"\bcredibility\b", "specificity", text, flags=re.IGNORECASE)
    text = re.sub(r"\bcredible\b", "specific", text, flags=re.IGNORECASE)
    text = re.sub(r"\bbelievable\b", "detailed", text, flags=re.IGNORECASE)
    text = re.sub(r"\btruthfulness\b", "narrative structure", text, flags=re.IGNORECASE)
    text = re.sub(r"\btruthful\b", "structured", text, flags=re.IGNORECASE)
    text = re.sub(r"\bdeceptive\b", "divergent", text, flags=re.IGNORECASE)
    text = re.sub(r"\bdeception\b", "discrepancy", text, flags=re.IGNORECASE)
    text = re.sub(r"\b(?:lying|liar)\b", "inconsistent statement", text, flags=re.IGNORECASE)

    # Clean up any double spaces introduced by replacements
    text = re.sub(r"\s{2,}", " ", text).strip()
    return text


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
    cannot have hallucinated scores or advice. Also prevents duplicate advice across categories
    and sanitizes all qualitative statements to ensure strictly evidence-grounded language.
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
            if "range" not in obs and "reference" not in obs and "movement" not in obs.lower() and "supporting data" not in obs.lower():
                bl_item["evidence_observation"] = f"Supporting data: {hm_rate:.1f} movements/min (reference: 15-35/min) | {obs}".strip(" |")

    # 3. Engagement / Camera presence requires camera tracking
    if not has_valid_visual:
        eval_data["engagement"] = {
            "score": "Insufficient Data",
            "metric_name": "Camera Presence",
            "assessment": "Camera presence signals require active camera tracking to measure face visibility.",
            "evidence_observation": "No facial landmark stream available. Camera presence is unmeasured.",
            "what_went_well": "N/A",
            "what_needs_improvement": "N/A",
            "practical_recommendation": "Position yourself centered in the camera viewport with clear lighting."
        }

    # 4. Confidence indicators require multimodal delivery signals
    if not has_valid_speech and not has_valid_visual:
        eval_data["confidence_indicators"] = {
            "score": "Insufficient Data",
            "metric_name": "Delivery Composure",
            "assessment": "Insufficient multimodal behavioral signals to evaluate delivery composure.",
            "evidence_observation": "Acoustic and visual streams lack sufficient measurable signals.",
            "what_went_well": "N/A",
            "what_needs_improvement": "N/A",
            "practical_recommendation": "Record both clear microphone audio and forward-facing video."
        }

    # 5. Story quality / Narrative detail requires transcript
    if not has_valid_transcript:
        eval_data["story_quality"] = {
            "score": "Insufficient Data",
            "metric_name": "Narrative Detail",
            "assessment": "No transcript available to evaluate narrative detail.",
            "evidence_observation": "Missing textual account. Narrative detail is unmeasured.",
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
        sq["what_needs_improvement"] = "Strengthen narrative chronology and event transitions so the listener can follow the progression effortlessly."
        sq["practical_recommendation"] = "Keep using specific examples, and connect events with clear sequence markers like 'first', 'then', and 'after that'."

    # Sanitize every field to guarantee strict grounding in measured metrics
    for cat_key, item in eval_data.items():
        if isinstance(item, dict):
            for field in ("assessment", "evidence_observation", "what_went_well", "what_needs_improvement", "practical_recommendation"):
                if field in item and isinstance(item[field], str):
                    item[field] = _sanitize_assessment_text(item[field])

    # Ensure any category with "Insufficient Data" has "N/A" for what_went_well and what_needs_improvement
    for k, item in eval_data.items():
        if isinstance(item, dict) and item.get("score") == "Insufficient Data":
            item["what_went_well"] = "N/A"
            item["what_needs_improvement"] = "N/A"

    return eval_data


def _deterministic_evaluation(
    person_name: str,
    transcript: str,
    story_data: Optional[dict] = None,
    speech_feats: Optional[dict] = None,
    visual_feats: Optional[dict] = None,
    profile_key: Optional[str] = None
) -> dict:
    from analytical_engine.evaluator import compute_deterministic_scores
    from processors.context_engine.weighting import get_context_profile
    prof = get_context_profile(profile_key)
    return compute_deterministic_scores(
        person_name=person_name,
        transcript=transcript,
        story_data=story_data,
        speech_feats=speech_feats,
        visual_feats=visual_feats,
        profile=prof
    )

