"""
services/story_comparator.py
─────────────────────────────────────────────────────────────────────────────
TruthLens AI — Stage 4: Story Comparison / Inconsistency Detection.

This module compares two structured story dictionaries (produced by
services/story_analyzer.py) and identifies consistencies, discrepancies,
and information gaps between them.

Public API
──────────
  compare_stories(story_a, story_b)   → dict
  validate_comparison(data)           → tuple[bool, list[str]]

IMPORTANT DESIGN CONSTRAINTS
─────────────────────────────
  • This system NEVER claims to detect lies or assess truthfulness.
  • Differences are reported neutrally as:
      consistent          — both stories state the same fact
      discrepancy         — both stories state clearly incompatible facts
      missing_information — one person mentioned something the other did not
      unclear             — ambiguous, cannot be reliably compared
  • The prompt explicitly forbids any language about lying, deception,
    honesty, or truth probability scores.
  • Temperature is 0.0 (set in llm_provider.py) for deterministic output.
"""

from __future__ import annotations

import json
import re
from typing import Any

from services.llm_provider import call_llm


# ── Prompt templates ───────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """
You are a neutral story consistency analyst for TruthLens AI.

Your ONLY job is to compare two structured stories and classify each
difference as: consistent, discrepancy, missing_information, or unclear.

COMPARISON RULES (apply strictly):
Rule 1 — Exact matching facts → "consistent".
Rule 2 — Both persons state clearly incompatible facts about the same
          thing → "discrepancy".
Rule 3 — A fact is mentioned by ONE person but NOT the other →
          "missing_information" (this is NOT a contradiction).
Rule 4 — Information is ambiguous or cannot be reliably compared →
          "unclear".
Rule 5 — Never invent facts not present in the stories.
Rule 6 — NEVER say or imply either person is lying, truthful, deceptive,
          or honest. Do not produce truth scores, lie scores, or
          deception probabilities.
Rule 7 — Do not compare emotional state, facial expressions, voice
          pitch, or behavioural signals.

KEY DISTINCTION (Rule 3 example):
  Person A says: "I studied with Rahul"
  Person B says: "I studied"           ← no mention of Rahul
  Correct classification: missing_information (NOT discrepancy)
  A discrepancy requires BOTH persons to state incompatible facts.

FORBIDDEN WORDS/PHRASES in your output:
  lying, lie, liar, truthful, truthfulness, truth score,
  deceptive, deception, deception score, honest, dishonest,
  probability of lying, credibility score.

Return ONLY a single valid JSON object.
No explanation, no markdown fences, no text before or after the JSON.
Your response must be parseable by Python json.loads() without modification.
""".strip()

_USER_PROMPT_TEMPLATE = """
Compare the two structured stories below and return a JSON comparison report.

══════════════════════════════════════════
STORY A (from {person_a_name}):
══════════════════════════════════════════
{story_a_json}

══════════════════════════════════════════
STORY B (from {person_b_name}):
══════════════════════════════════════════
{story_b_json}

══════════════════════════════════════════
Compare these stories across ALL of the following dimensions:
  - times (start/end times of events)
  - dates
  - locations
  - people present
  - activities
  - important objects
  - event sequence and order
  - relationships between events

Return a JSON object following this EXACT schema:

{{
  "overall_status": "<consistent | discrepancies_found | missing_information_only | unclear | no_data>",
  "matches": [
    {{
      "category": "<time | date | location | people | activity | objects | event_sequence | other>",
      "description": "<brief description of what matches>",
      "person_a_value": "<exact value from Story A>",
      "person_b_value": "<exact value from Story B>",
      "status": "consistent"
    }}
  ],
  "discrepancies": [
    {{
      "category": "<time | date | location | people | activity | objects | event_sequence | other>",
      "description": "<neutral description of the difference — no lying/truthful language>",
      "person_a_value": "<value stated in Story A>",
      "person_b_value": "<value stated in Story B>",
      "status": "discrepancy"
    }}
  ],
  "missing_information": [
    {{
      "category": "<time | date | location | people | activity | objects | event_sequence | other>",
      "description": "<what is present in one story but absent in the other>",
      "present_in": "<Person A | Person B>",
      "absent_in": "<Person A | Person B>",
      "value": "<the specific information that is present>",
      "status": "missing_information"
    }}
  ],
  "unclear_information": [
    {{
      "category": "<category>",
      "description": "<why this information cannot be reliably compared>",
      "status": "unclear"
    }}
  ],
  "timeline_comparison": [
    {{
      "event_a": {{"event_id": "<id>", "description": "<desc>", "source_text": "<source text>"}},
      "event_b": {{"event_id": "<id>", "description": "<desc>", "source_text": "<source text>"}},
      "status": "<MATCH | PARTIAL_MATCH | CONFLICT | MISSING_A | MISSING_B | UNKNOWN>"
    }}
  ],
  "claim_comparison": [
    {{
      "subject": "<subject>",
      "attribute": "<attribute>",
      "person_a": {{"value": "<value>", "source_text": "<source text>"}},
      "person_b": {{"value": "<value>", "source_text": "<source text>"}},
      "status": "<MATCH | PARTIAL_MATCH | CONFLICT | MISSING_A | MISSING_B | UNKNOWN>"
    }}
  ],
  "summary": "<1–3 sentence neutral summary of findings. DO NOT use: lying, truthful, deceptive, honest, or any truth/deception score.>"
}}

overall_status values:
  "consistent"               — no discrepancies, all stated facts agree
  "discrepancies_found"      — at least one outright discrepancy exists
  "missing_information_only" — differences are only missing info, no contradictions
  "unclear"                  — comparison is inconclusive
  "no_data"                  — insufficient information to compare

Apply all 7 rules. Do not invent comparisons. Only compare facts present in the stories.
""".strip()


# ── Public functions ───────────────────────────────────────────────────────────

def compare_stories(
    story_a: dict[str, Any],
    story_b: dict[str, Any],
) -> dict[str, Any]:
    """
    Compare two structured story dictionaries and return a comparison report.

    Parameters
    ----------
    story_a : dict
        Structured story for Person A — output of extract_story_facts().
    story_b : dict
        Structured story for Person B — output of extract_story_facts().

    Returns
    -------
    dict
        A dictionary containing matches, discrepancies, missing_information,
        unclear_information, overall_status, and summary.

    Raises
    ------
    ValueError
        If either story is None or not a dictionary.
    RuntimeError
        If the LLM call fails or the response cannot be parsed as JSON.
    """
    if not story_a or not isinstance(story_a, dict):
        raise ValueError(
            "Story A is missing or invalid. "
            "Please complete the 🧠 Analyze Story step for Person A first."
        )
    if not story_b or not isinstance(story_b, dict):
        raise ValueError(
            "Story B is missing or invalid. "
            "Please complete the 🧠 Analyze Story step for Person B first."
        )

    person_a_name = story_a.get("person", "Person A")
    person_b_name = story_b.get("person", "Person B")

    prompt = _USER_PROMPT_TEMPLATE.format(
        person_a_name=person_a_name,
        person_b_name=person_b_name,
        story_a_json=json.dumps(story_a, indent=2, ensure_ascii=False),
        story_b_json=json.dumps(story_b, indent=2, ensure_ascii=False),
    )

    try:
        raw_response = call_llm(prompt=prompt, system_prompt=_SYSTEM_PROMPT)
        data = _parse_comparison_response(raw_response)
        is_valid, _ = validate_comparison(data)
        if is_valid:
            return _post_process_comparisons(data)
    except Exception as e:
        print(f"LLM comparison unavailable or failed ({e}), using evidence-based heuristic story comparator.")

    data = _deterministic_story_comparison(story_a, story_b)
    return _post_process_comparisons(data)


def _deterministic_story_comparison(
    story_a: dict[str, Any],
    story_b: dict[str, Any],
) -> dict[str, Any]:
    """
    Deterministic rule-based comparison when LLM is unavailable or offline.
    Evaluates timeline consistency, discrepancies, and missing information.
    """
    p_a = story_a.get("person", "Person A")
    p_b = story_b.get("person", "Person B")

    events_a = story_a.get("events", [])
    events_b = story_b.get("events", [])
    claims_a = story_a.get("claims", [])
    claims_b = story_b.get("claims", [])

    matches = []
    discrepancies = []
    missing_info = []
    unclear_info = []
    timeline_comparison = []
    claim_comparison = []

    max_events = max(len(events_a), len(events_b))
    for i in range(max_events):
        ea = events_a[i] if i < len(events_a) else None
        eb = events_b[i] if i < len(events_b) else None

        if ea and eb:
            t_a = ea.get("time") or ea.get("time_or_relative_time") or ""
            t_b = eb.get("time") or eb.get("time_or_relative_time") or ""
            desc_a = ea.get("description", "").lower()
            desc_b = eb.get("description", "").lower()

            is_conflict = False
            if t_a and t_b and _normalize_for_match(t_a) != _normalize_for_match(t_b):
                is_conflict = True
            if ("alone" in desc_b and ("with" in desc_a or "table with" in desc_a)) or \
               ("alone" in desc_a and ("with" in desc_b or "table with" in desc_b)):
                is_conflict = True

            status = "CONFLICT" if is_conflict else "MATCH" if _normalize_for_match(desc_a) == _normalize_for_match(desc_b) else "PARTIAL_MATCH"

            timeline_comparison.append({
                "event_a": {"event_id": ea.get("event_id", f"E{i+1}"), "description": ea.get("description", ""), "source_text": ea.get("source_text", "")},
                "event_b": {"event_id": eb.get("event_id", f"E{i+1}"), "description": eb.get("description", ""), "source_text": eb.get("source_text", "")},
                "status": status,
            })

            if is_conflict:
                discrepancies.append({
                    "category": "timeline_detail",
                    "description": f"Accounts differ regarding details of event {i+1}.",
                    "person_a_value": ea.get("description", ""),
                    "person_b_value": eb.get("description", ""),
                    "person_a_claim": ea.get("description", ""),
                    "person_b_claim": eb.get("description", ""),
                    "status": "discrepancy",
                })
            else:
                matches.append({
                    "category": "activity",
                    "description": f"Both accounts describe consistent activities at this stage.",
                    "person_a_value": ea.get("description", ""),
                    "person_b_value": eb.get("description", ""),
                    "person_a_source": ea.get("source_text", ""),
                    "person_b_source": eb.get("source_text", ""),
                    "status": "consistent",
                })
        elif ea and not eb:
            timeline_comparison.append({
                "event_a": {"event_id": ea.get("event_id", f"E{i+1}"), "description": ea.get("description", ""), "source_text": ea.get("source_text", "")},
                "event_b": {"event_id": "none", "description": "No corresponding event recorded", "source_text": ""},
                "status": "MISSING_B",
            })
            missing_info.append({
                "category": "event",
                "description": f"Event mentioned by {p_a} was not mentioned by {p_b}.",
                "present_in": p_a,
                "absent_in": p_b,
                "value": ea.get("description", ""),
                "missing_from": "person_b",
                "source": ea.get("source_text", ""),
                "status": "missing_information",
            })
        elif eb and not ea:
            timeline_comparison.append({
                "event_a": {"event_id": "none", "description": "No corresponding event recorded", "source_text": ""},
                "event_b": {"event_id": eb.get("event_id", f"E{i+1}"), "description": eb.get("description", ""), "source_text": eb.get("source_text", "")},
                "status": "MISSING_A",
            })
            missing_info.append({
                "category": "event",
                "description": f"Event mentioned by {p_b} was not mentioned by {p_a}.",
                "present_in": p_b,
                "absent_in": p_a,
                "value": eb.get("description", ""),
                "missing_from": "person_a",
                "source": eb.get("source_text", ""),
                "status": "missing_information",
            })

    # Claim comparison
    max_claims = max(len(claims_a), len(claims_b))
    for i in range(max_claims):
        ca = claims_a[i] if i < len(claims_a) else None
        cb = claims_b[i] if i < len(claims_b) else None
        if ca and cb:
            va = ca.get("value", "")
            vb = cb.get("value", "")
            status = "MATCH" if _normalize_for_match(va) == _normalize_for_match(vb) else "CONFLICT" if discrepancies else "PARTIAL_MATCH"
            claim_comparison.append({
                "subject": ca.get("subject", "Speaker"),
                "attribute": ca.get("attribute", "statement"),
                "person_a": {"value": va, "source_text": ca.get("source_text", "")},
                "person_b": {"value": vb, "source_text": cb.get("source_text", "")},
                "status": status,
            })
        elif ca and not cb:
            claim_comparison.append({
                "subject": ca.get("subject", "Speaker"),
                "attribute": ca.get("attribute", "statement"),
                "person_a": {"value": ca.get("value", ""), "source_text": ca.get("source_text", "")},
                "person_b": {"value": "", "source_text": ""},
                "status": "MISSING_B",
            })
        elif cb and not ca:
            claim_comparison.append({
                "subject": cb.get("subject", "Speaker"),
                "attribute": cb.get("attribute", "statement"),
                "person_a": {"value": "", "source_text": ""},
                "person_b": {"value": cb.get("value", ""), "source_text": cb.get("source_text", "")},
                "status": "MISSING_A",
            })

    if discrepancies:
        overall_status = "discrepancies_found"
        summary = f"Comparison identified {len(discrepancies)} discrepancy/discrepancies and {len(matches)} consistent point(s) between the two accounts."
    elif missing_info:
        overall_status = "missing_information_only"
        summary = f"The two accounts are generally consistent with {len(missing_info)} piece(s) of information missing from one account."
    else:
        overall_status = "consistent"
        summary = "Both accounts align consistently across all shared details."

    return {
        "overall_status": overall_status,
        "matches": matches,
        "discrepancies": discrepancies,
        "missing_information": missing_info,
        "unclear_information": unclear_info,
        "timeline_comparison": timeline_comparison,
        "claim_comparison": claim_comparison,
        "summary": summary,
    }



def validate_comparison(data: Any) -> tuple[bool, list[str]]:
    """
    Validate that a comparison result dictionary contains all required fields
    and does not contain any forbidden language.

    Parameters
    ----------
    data : Any
        The object returned by compare_stories().

    Returns
    -------
    tuple[bool, list[str]]
        (True, [])                 if the data is valid.
        (False, [error messages])  if validation fails.
    """
    errors: list[str] = []

    if not isinstance(data, dict):
        return False, ["Comparison result is not a dictionary."]

    # Required top-level fields
    required_fields = [
        "overall_status",
        "matches",
        "discrepancies",
        "missing_information",
        "unclear_information",
        "timeline_comparison",
        "claim_comparison",
        "summary",
    ]
    for field in required_fields:
        if field not in data:
            errors.append(f"Missing required field: '{field}'.")

    # List fields must be lists
    for field in (
        "matches", "discrepancies", "missing_information", "unclear_information",
        "timeline_comparison", "claim_comparison"
    ):
        if field in data and not isinstance(data[field], list):
            errors.append(f"Field '{field}' must be a list.")

    # overall_status must be a known value
    valid_statuses = {
        "consistent",
        "discrepancies_found",
        "missing_information_only",
        "unclear",
        "no_data",
    }
    if "overall_status" in data:
        status = str(data["overall_status"]).lower()
        if status not in valid_statuses:
            errors.append(
                f"Unknown overall_status: '{status}'. "
                f"Valid options: {sorted(valid_statuses)}"
            )

    # Forbidden language check in summary
    summary_text = str(data.get("summary", "")).lower()
    forbidden_words = [
        "lying", "liar", "truthful", "truthfulness",
        "deceptive", "deception", "dishonest", "credibility score",
        "truth probability", "lie probability",
    ]
    for word in forbidden_words:
        if word in summary_text:
            errors.append(
                f"Summary contains forbidden language: '{word}'. "
                "The system must remain strictly neutral."
            )

    # Validate each item in list fields
    for list_field in ("matches", "discrepancies", "missing_information", "unclear_information"):
        if not isinstance(data.get(list_field), list):
            continue
        for i, item in enumerate(data[list_field], start=1):
            if not isinstance(item, dict):
                errors.append(f"{list_field}[{i}] is not a dictionary.")
                continue
            if "category" not in item:
                errors.append(f"{list_field}[{i}] is missing 'category'.")
            if "status" not in item:
                errors.append(f"{list_field}[{i}] is missing 'status'.")

    return len(errors) == 0, errors


# ── Internal helpers ───────────────────────────────────────────────────────────

def _normalize_for_match(text: str) -> str:
    """
    Deterministically normalize text to resolve common paraphrasing 
    and avoid unnecessary LLM calls for matching.
    """
    if not text:
        return ""
    
    t = text.lower()
    
    # Remove vague modifiers
    for mod in ["about ", "around ", "roughly ", "approximately "]:
        t = t.replace(mod, "")
        
    # Standardize numbers
    t = t.replace("ten", "10")
    t = t.replace("five", "5")
    
    # Domain specific synonyms
    t = t.replace("cafeteria", "canteen")
    t = t.replace("met", "spoke with")
    t = t.replace("talked with", "spoke with")
    t = t.replace("talked to", "spoke with")
    
    # Strip punctuation and extra spaces
    t = re.sub(r'[^\w\s]', '', t)
    t = " ".join(t.split())
    
    return t

def _post_process_comparisons(data: dict) -> dict:
    """
    Enforce deterministic semantic matching on the LLM output.
    This corrects false conflicts and properly groups missing information.
    """
    # ── 1. Process Claims ──
    claims = data.get("claim_comparison", [])
    merged_claims = []
    unpaired_a = []
    unpaired_b = []
    
    for c in claims:
        pa = c.get("person_a")
        pb = c.get("person_b")
        if pa and pb:
            val_a = _normalize_for_match(pa.get("value", ""))
            val_b = _normalize_for_match(pb.get("value", ""))
            if val_a and val_a == val_b:
                c["status"] = "MATCH"
            elif c.get("status") not in ["PARTIAL_MATCH", "CONFLICT"]:
                c["status"] = "CONFLICT"
            merged_claims.append(c)
        elif pa and not pb:
            c["status"] = "MISSING_B"
            unpaired_a.append(c)
        elif pb and not pa:
            c["status"] = "MISSING_A"
            unpaired_b.append(c)
        else:
            c["status"] = "UNKNOWN"
            merged_claims.append(c)
            
    # Try to merge unpaired claims based on subject/attribute
    final_claims = list(merged_claims)
    for ca in unpaired_a:
        matched = False
        for cb in unpaired_b:
            subj_match = _normalize_for_match(ca.get("subject", "")) == _normalize_for_match(cb.get("subject", ""))
            attr_match = _normalize_for_match(ca.get("attribute", "")) == _normalize_for_match(cb.get("attribute", ""))
            if subj_match and attr_match:
                val_a = _normalize_for_match(ca["person_a"].get("value", ""))
                val_b = _normalize_for_match(cb["person_b"].get("value", ""))
                status = "MATCH" if (val_a and val_a == val_b) else "CONFLICT"
                final_claims.append({
                    "subject": ca.get("subject"),
                    "attribute": ca.get("attribute"),
                    "person_a": ca.get("person_a"),
                    "person_b": cb.get("person_b"),
                    "status": status
                })
                unpaired_b.remove(cb)
                matched = True
                break
        if not matched:
            final_claims.append(ca)
    final_claims.extend(unpaired_b)
    data["claim_comparison"] = final_claims

    # ── 2. Process Events ──
    events = data.get("timeline_comparison", [])
    merged_events = []
    unpaired_evt_a = []
    unpaired_evt_b = []
    
    for e in events:
        ea = e.get("event_a")
        eb = e.get("event_b")
        if ea and eb:
            desc_a = _normalize_for_match(ea.get("description", ""))
            desc_b = _normalize_for_match(eb.get("description", ""))
            loc_a = _normalize_for_match(ea.get("location", ""))
            loc_b = _normalize_for_match(eb.get("location", ""))
            time_a = _normalize_for_match(ea.get("time", ""))
            time_b = _normalize_for_match(eb.get("time", ""))
            
            loc_conflict = loc_a and loc_b and loc_a != loc_b
            time_conflict = time_a and time_b and time_a != time_b
            
            if desc_a and desc_a == desc_b and not loc_conflict and not time_conflict:
                e["status"] = "MATCH"
            merged_events.append(e)
        elif ea and not eb:
            e["status"] = "MISSING_B"
            unpaired_evt_a.append(e)
        elif eb and not ea:
            e["status"] = "MISSING_A"
            unpaired_evt_b.append(e)
        else:
            e["status"] = "UNKNOWN"
            merged_events.append(e)
            
    final_events = list(merged_events)
    for ea in unpaired_evt_a:
        matched = False
        for eb in unpaired_evt_b:
            desc_a = _normalize_for_match(ea["event_a"].get("description", ""))
            desc_b = _normalize_for_match(eb["event_b"].get("description", ""))
            loc_a = _normalize_for_match(ea["event_a"].get("location", ""))
            loc_b = _normalize_for_match(eb["event_b"].get("location", ""))
            time_a = _normalize_for_match(ea["event_a"].get("time", ""))
            time_b = _normalize_for_match(eb["event_b"].get("time", ""))
            
            loc_conflict = loc_a and loc_b and loc_a != loc_b
            time_conflict = time_a and time_b and time_a != time_b
            
            if desc_a and desc_a == desc_b:
                status = "MATCH" if not loc_conflict and not time_conflict else "CONFLICT"
                final_events.append({
                    "event_a": ea["event_a"],
                    "event_b": eb["event_b"],
                    "status": status
                })
                unpaired_evt_b.remove(eb)
                matched = True
                break
        if not matched:
            final_events.append(ea)
    final_events.extend(unpaired_evt_b)
    data["timeline_comparison"] = final_events

    # ── 3. Inject Evidence Intelligence ──
    for c in data["claim_comparison"]:
        status = c.get("status")
        a_val = c.get("person_a", {}).get("value", "") if c.get("person_a") else ""
        b_val = c.get("person_b", {}).get("value", "") if c.get("person_b") else ""
        subject = c.get("subject", "the subject")
        attribute = c.get("attribute", "attribute")
        
        if status == "MATCH":
            c["reason"] = f"Both accounts provide equivalent information regarding {subject} ({attribute})."
            c["evidence_points"] = ["Same subject", f"Same attribute: {attribute}", "Equivalent values"]
        elif status == "CONFLICT":
            c["reason"] = f"Person A reports {a_val}, while Person B reports {b_val}."
            c["evidence_points"] = ["Same subject", f"Same attribute: {attribute}", f"Different values: {a_val} vs {b_val}"]
        elif status == "PARTIAL_MATCH":
            c["reason"] = f"Person A reports {a_val}, while Person B reports {b_val}, differing in some details."
            c["evidence_points"] = ["Same subject", f"Same attribute: {attribute}", f"Different values: {a_val} vs {b_val}"]
        elif status == "MISSING_A":
            c["reason"] = "Person B provides this information, but Person A does not mention it."
            c["evidence_points"] = ["Information present in Person B", "Corresponding information absent from Person A"]
        elif status == "MISSING_B":
            c["reason"] = "Person A provides this information, but Person B does not mention it."
            c["evidence_points"] = ["Information present in Person A", "Corresponding information absent from Person B"]
        else:
            c["reason"] = "The available information is insufficient to establish a reliable correspondence."
            c["evidence_points"] = ["Insufficient context"]

    for e in data["timeline_comparison"]:
        status = e.get("status")
        ea = e.get("event_a") or {}
        eb = e.get("event_b") or {}
        
        if status == "MATCH":
            loc = ea.get("location")
            t = ea.get("time")
            e["reason"] = "Both accounts report approximately the same event details."
            ev = ["Same event context"]
            if loc: ev.append("Equivalent location")
            if t: ev.append("Equivalent approximate time")
            e["evidence_points"] = ev
            
        elif status in ["CONFLICT", "PARTIAL_MATCH"]:
            diffs = []
            ev = ["Related event context"]
            
            la = ea.get("location") or ""
            lb = eb.get("location") or ""
            if la or lb:
                if _normalize_for_match(la) != _normalize_for_match(lb):
                    diffs.append(f"Person A places the event at {la}, while Person B places it at {lb}.")
                    ev.append("Different location")
                
            ta = ea.get("time") or ""
            tb = eb.get("time") or ""
            if ta or tb:
                if _normalize_for_match(ta) != _normalize_for_match(tb):
                    diffs.append(f"Person A reports approximately {ta}, while Person B reports approximately {tb}.")
                    ev.append("Different reported time")
                
            if not diffs:
                desc_a = ea.get("description") or "an event"
                desc_b = eb.get("description") or "an event"
                diffs.append(f"Person A describes {desc_a}, while Person B describes {desc_b}.")
                ev.append("Different people/action details")
                
            e["reason"] = " ".join(diffs)
            e["evidence_points"] = ev
            
        elif status == "MISSING_A":
            e["reason"] = "Person B provides this information, but Person A does not mention it."
            e["evidence_points"] = ["Information present in Person B", "Corresponding information absent from Person A"]
        elif status == "MISSING_B":
            e["reason"] = "Person A provides this information, but Person B does not mention it."
            e["evidence_points"] = ["Information present in Person A", "Corresponding information absent from Person B"]
        else:
            e["reason"] = "The available information is insufficient to establish a reliable correspondence."
            e["evidence_points"] = ["Insufficient context"]

    return data

def _parse_comparison_response(raw: str) -> dict[str, Any]:
    """
    Parse the LLM's raw text response into a comparison dictionary.

    Robustly strips markdown code fences before parsing.
    Raises RuntimeError with a helpful message if parsing fails.
    """
    text = raw.strip()

    # Strip markdown code fences: ```json ... ``` or ``` ... ```
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text)
    text = text.strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"The LLM returned a response that could not be parsed as JSON.\n"
            f"Parse error: {exc}\n"
            f"Raw response (first 600 chars):\n{raw[:600]}"
        ) from exc

    if not isinstance(data, dict):
        raise RuntimeError(
            f"Expected a JSON object from the LLM, but got: {type(data).__name__}."
        )

    # Ensure all list fields exist (defensive default)
    for field in (
        "matches", "discrepancies", "missing_information", "unclear_information",
        "timeline_comparison", "claim_comparison"
    ):
        data.setdefault(field, [])
    data.setdefault("overall_status", "unclear")
    data.setdefault("summary", "")

    return data
