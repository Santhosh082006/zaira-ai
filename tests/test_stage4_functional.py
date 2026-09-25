"""
TruthLens AI — Stage 4 Functional Test
========================================
Tests services/story_comparator.py against the live OpenRouter API
using pre-built story dicts (no microphone, no audio, no Stage 4+).

The mock stories mirror what extract_story_facts() would produce for
each transcript, so we test the comparator in isolation.

Run:
    python test_stage4_functional.py
"""

from __future__ import annotations

import json
import os
import sys
import time

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from dotenv import load_dotenv

load_dotenv(os.path.join(ROOT_DIR, ".env"))

from services.story_comparator import compare_stories, validate_comparison
from services.llm_provider import get_active_provider

# ── ANSI helpers ───────────────────────────────────────────────────────────────
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

def ok(msg):   print(f"  {GREEN}PASS{RESET}  {msg}")
def fail(msg): print(f"  {RED}FAIL{RESET}  {msg}")
def info(msg): print(f"  {CYAN}INFO{RESET}  {msg}")
def sep(title=""):
    line = "=" * 66
    print(f"\n{BOLD}{line}{RESET}")
    if title:
        print(f"{BOLD}  {title}{RESET}")
        print(line)

# ── Mock story builder ─────────────────────────────────────────────────────────

def make_story(person, events, people=None, locations=None, times=None,
               dates=None, summary="", confidence="high", claims=None):
    """Construct a mock story dict matching the Stage 3 extraction schema."""
    return {
        "person":                  person,
        "summary":                 summary,
        "events":                  events    or [],
        "claims":                  claims    or [],
        "all_people_mentioned":    people    or [],
        "all_locations_mentioned": locations or [],
        "all_times_mentioned":     times     or [],
        "all_dates_mentioned":     dates     or [],
        "extraction_confidence":   confidence,
    }

def event(eid, sequence=1, action=None, location=None, time=None, time_normalized=None,
          people=None, description="Test event", source_text="Test source"):
    return {
        "event_id":  eid,
        "sequence":  sequence,
        "time":      time,
        "time_normalized": time_normalized,
        "location":  location,
        "people":    people  or [],
        "action":    action,
        "description": description,
        "source_text": source_text
    }


# ── Test cases ─────────────────────────────────────────────────────────────────

TEST_CASES = [

    # ──────────────────────────────────────────────────────────────────────────
    {
        "id": "TEST 1",
        "label": "Identical stories — expect: fully consistent",
        "story_a": make_story(
            person="Person A",
            summary="Person A studied in the library with Rahul at 7 PM yesterday.",
            events=[event(1, "studying", "library", "7 PM", None, "yesterday", ["Rahul"])],
            people=["Rahul"], locations=["library"], times=["7 PM"], dates=["yesterday"],
        ),
        "story_b": make_story(
            person="Person B",
            summary="Person B studied in the library with Rahul at 7 PM yesterday.",
            events=[event(1, "studying", "library", "7 PM", None, "yesterday", ["Rahul"])],
            people=["Rahul"], locations=["library"], times=["7 PM"], dates=["yesterday"],
        ),
        "expect": {
            "overall_status_must_be": ["consistent"],
            "min_matches":   1,
            "max_discrepancies": 0,
        },
    },

    # ──────────────────────────────────────────────────────────────────────────
    {
        "id": "TEST 2",
        "label": "Location discrepancy — expect: library vs canteen flagged",
        "story_a": make_story(
            person="Person A",
            summary="Person A studied in the library at 7 PM yesterday.",
            events=[event(1, "studying", "library", "7 PM", None, "yesterday")],
            locations=["library"], times=["7 PM"], dates=["yesterday"],
        ),
        "story_b": make_story(
            person="Person B",
            summary="Person B studied in the canteen at 7 PM yesterday.",
            events=[event(1, "studying", "canteen", "7 PM", None, "yesterday")],
            locations=["canteen"], times=["7 PM"], dates=["yesterday"],
        ),
        "expect": {
            "overall_status_must_be": ["discrepancies_found"],
            "min_discrepancies": 1,
            "discrepancy_category_must_include": ["location"],
        },
    },

    # ──────────────────────────────────────────────────────────────────────────
    {
        "id": "TEST 3",
        "label": "Missing person — expect: Rahul = missing_information NOT discrepancy",
        "story_a": make_story(
            person="Person A",
            summary="Person A studied in the library with Rahul at 7 PM yesterday.",
            events=[event(1, "studying", "library", "7 PM", None, "yesterday", ["Rahul"])],
            people=["Rahul"], locations=["library"], times=["7 PM"], dates=["yesterday"],
        ),
        "story_b": make_story(
            person="Person B",
            summary="Person B studied in the library at 7 PM yesterday.",
            events=[event(1, "studying", "library", "7 PM", None, "yesterday")],
            people=[], locations=["library"], times=["7 PM"], dates=["yesterday"],
        ),
        "expect": {
            "overall_status_must_be": ["missing_information_only", "discrepancies_found"],
            "min_missing": 1,
            # Critical: Rahul must appear in missing_information, not discrepancies
            "missing_value_must_include": ["Rahul", "rahul"],
            "rahul_must_not_be_discrepancy": True,
        },
    },

    # ──────────────────────────────────────────────────────────────────────────
    {
        "id": "TEST 4",
        "label": "Time discrepancy — expect: 7 PM vs 9 PM flagged",
        "story_a": make_story(
            person="Person A",
            summary="Person A studied in the library at 7 PM.",
            events=[event(1, "studying", "library", "7 PM")],
            locations=["library"], times=["7 PM"],
        ),
        "story_b": make_story(
            person="Person B",
            summary="Person B studied in the library at 9 PM.",
            events=[event(1, "studying", "library", "9 PM")],
            locations=["library"], times=["9 PM"],
        ),
        "expect": {
            "overall_status_must_be": ["discrepancies_found"],
            "min_discrepancies": 1,
            "discrepancy_category_must_include": ["time"],
        },
    },

    # ──────────────────────────────────────────────────────────────────────────
    {
        "id": "TEST 5",
        "label": "Event sequence discrepancy — library then mess vs mess then library",
        "story_a": make_story(
            person="Person A",
            summary="Person A went to the library and then to the mess.",
            events=[
                event(1, "went to library", "library", "7 PM"),
                event(2, "went to mess",    "hostel mess", "8 PM"),
            ],
            locations=["library", "hostel mess"], times=["7 PM", "8 PM"],
        ),
        "story_b": make_story(
            person="Person B",
            summary="Person B went to the mess and then to the library.",
            events=[
                event(1, "went to mess",    "hostel mess", "7 PM"),
                event(2, "went to library", "library",     "8 PM"),
            ],
            locations=["hostel mess", "library"], times=["7 PM", "8 PM"],
        ),
        "expect": {
            "overall_status_must_be": ["discrepancies_found"],
            "min_discrepancies": 1,
            "discrepancy_category_must_include": ["event_sequence", "location", "time"],
        },
    },
]


# ── Assertion helpers ──────────────────────────────────────────────────────────

def assert_status(data: dict, allowed: list[str]) -> bool:
    actual = str(data.get("overall_status", "")).lower()
    if actual in allowed:
        ok(f"overall_status = '{actual}'  (expected one of {allowed})")
        return True
    fail(f"overall_status = '{actual}'  — expected one of {allowed}")
    return False

def assert_min_count(data: dict, field: str, minimum: int) -> bool:
    count = len(data.get(field, []))
    if count >= minimum:
        ok(f"{field} count = {count}  (>= {minimum})")
        return True
    fail(f"{field} count = {count}  (expected >= {minimum})")
    return False

def assert_max_count(data: dict, field: str, maximum: int) -> bool:
    count = len(data.get(field, []))
    if count <= maximum:
        ok(f"{field} count = {count}  (<= {maximum})")
        return True
    fail(f"{field} count = {count}  (expected <= {maximum})")
    return False

def assert_discrepancy_category(data: dict, must_include: list[str]) -> bool:
    cats = [str(d.get("category", "")).lower() for d in data.get("discrepancies", [])]
    combined = " | ".join(cats)
    for cat in must_include:
        if any(cat.lower() in c for c in cats):
            ok(f"discrepancy category '{cat}' found")
            return True
    fail(f"None of {must_include} found in discrepancy categories: {cats!r}")
    return False

def assert_missing_value(data: dict, must_include: list[str]) -> bool:
    # Check all_value fields and description fields in missing_information
    missing_text = " | ".join(
        f"{m.get('value','')} {m.get('description','')}".lower()
        for m in data.get("missing_information", [])
    )
    for val in must_include:
        if val.lower() in missing_text:
            ok(f"missing_information contains '{val}'")
            return True
    fail(f"None of {must_include} found in missing_information: {missing_text!r}")
    return False

def assert_rahul_not_discrepancy(data: dict) -> bool:
    disc_text = " | ".join(
        f"{d.get('person_a_value','')} {d.get('person_b_value','')} {d.get('description','')}".lower()
        for d in data.get("discrepancies", [])
    )
    if "rahul" in disc_text:
        fail("'Rahul' appears in discrepancies — should be missing_information only!")
        return False
    ok("'Rahul' correctly NOT classified as a discrepancy")
    return True

def assert_no_forbidden_language(data: dict) -> bool:
    full_text = json.dumps(data).lower()
    forbidden = ["lying", "liar", "truthful", "deceptive", "deception", "dishonest"]
    found = [w for w in forbidden if w in full_text]
    if found:
        fail(f"Forbidden language found in result: {found}")
        return False
    ok("No forbidden language (lying/truthful/deceptive) in result")
    return True


def run_tests():
    # ── Pre-flight ─────────────────────────────────────────────────────────────────
    sep("TruthLens AI -- Stage 4 Functional Test")
    provider = get_active_provider()
    model    = os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini")
    api_key  = os.getenv("OPENROUTER_API_KEY", "").strip()
    info(f"Provider : {provider}")
    info(f"Model    : {model}")
    info(f"API key  : {'SET (...' + api_key[-6:] + ')' if api_key else 'NOT SET'}")

    if not api_key and provider == "openrouter":
        print(f"\n{RED}ERROR: OPENROUTER_API_KEY not set.{RESET}")
        sys.exit(1)

    overall_passed = 0
    overall_failed = 0

    for tc in TEST_CASES:
        sep(f"{tc['id']} -- {tc['label']}")

        t_start = time.time()
        try:
            data = compare_stories(tc["story_a"], tc["story_b"])
            elapsed = time.time() - t_start
            ok(f"API call succeeded ({elapsed:.1f}s)")
        except Exception as exc:
            elapsed = time.time() - t_start
            fail(f"API call FAILED after {elapsed:.1f}s: {exc}")
            overall_failed += 1
            continue

        # Schema validation
        is_valid, errs = validate_comparison(data)
        if is_valid:
            ok("validate_comparison() -> PASS")
        else:
            for e in errs:
                fail(f"Validation: {e}")

        # Assertions
        exp = tc["expect"]
        checks = []

        checks.append(assert_status(data, exp.get("overall_status_must_be", [])))

        if "min_matches" in exp:
            checks.append(assert_min_count(data, "matches", exp["min_matches"]))
        if "max_discrepancies" in exp:
            checks.append(assert_max_count(data, "discrepancies", exp["max_discrepancies"]))
        if "min_discrepancies" in exp:
            checks.append(assert_min_count(data, "discrepancies", exp["min_discrepancies"]))
        if "min_missing" in exp:
            checks.append(assert_min_count(data, "missing_information", exp["min_missing"]))
        if "discrepancy_category_must_include" in exp:
            checks.append(assert_discrepancy_category(data, exp["discrepancy_category_must_include"]))
        if "missing_value_must_include" in exp:
            checks.append(assert_missing_value(data, exp["missing_value_must_include"]))
        if exp.get("rahul_must_not_be_discrepancy"):
            checks.append(assert_rahul_not_discrepancy(data))

        checks.append(assert_no_forbidden_language(data))

        # Print JSON
        print()
        info("Comparison JSON:")
        print(json.dumps(data, indent=2, ensure_ascii=False))

        tc_pass = all(checks) and is_valid
        label_str = f"{GREEN}PASSED{RESET}" if tc_pass else f"{RED}FAILED{RESET}"
        print(f"\n  {tc['id']} result: {label_str}")
        if tc_pass:
            overall_passed += 1
        else:
            overall_failed += 1

    # ── Final summary ──────────────────────────────────────────────────────────────
    sep("FINAL SUMMARY")
    total = overall_passed + overall_failed
    print(f"  Tests run    : {total}")
    print(f"  {GREEN}Passed{RESET}       : {overall_passed}")
    print(f"  {RED}Failed{RESET}       : {overall_failed}")
    print("=" * 66)
    sys.exit(0 if overall_failed == 0 else 1)


if __name__ == "__main__":
    run_tests()
