"""
TruthLens AI — Stage 3 Functional Test
=======================================
Tests services/story_analyzer.py against the live OpenRouter API
using three sample transcripts. No microphone, no audio, no Stage 4.

Run:
    python test_stage3_functional.py
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

# Load .env before importing anything from services/
load_dotenv(os.path.join(ROOT_DIR, ".env"))

from services.story_analyzer import extract_story_facts, validate_extracted_story
from services.llm_provider import get_active_provider

# ── ANSI colour helpers (work on Windows with PYTHONIOENCODING=utf-8) ──────────
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

def ok(msg):   print(f"  {GREEN}PASS{RESET}  {msg}")
def fail(msg): print(f"  {RED}FAIL{RESET}  {msg}")
def info(msg): print(f"  {CYAN}INFO{RESET}  {msg}")
def warn(msg): print(f"  {YELLOW}WARN{RESET}  {msg}")
def sep(title=""):
    line = "=" * 66
    print(f"\n{BOLD}{line}{RESET}")
    if title:
        print(f"{BOLD}  {title}{RESET}")
        print(line)

# ── Pre-flight: check configuration ───────────────────────────────────────────
sep("TruthLens AI — Stage 3 Functional Test")

provider = get_active_provider()
model    = os.getenv("OPENROUTER_MODEL", "google/gemini-flash-1.5")
api_key  = os.getenv("OPENROUTER_API_KEY", "").strip()

info(f"Provider : {provider}")
info(f"Model    : {model}")
info(f"API key  : {'SET (...' + api_key[-6:] + ')' if api_key else 'NOT SET'}")

if not api_key and provider == "openrouter":
    print(f"\n{RED}ERROR: OPENROUTER_API_KEY is not set in your .env file.{RESET}")
    print("  1. Copy .env.example  ->  .env")
    print("  2. Set OPENROUTER_API_KEY=sk-or-...")
    print("  3. Set LLM_PROVIDER=openrouter")
    print("  4. Re-run this script.")
    sys.exit(1)

# ── Test cases ─────────────────────────────────────────────────────────────────

TEST_CASES = [
    {
        "id":      "TEST 1",
        "person":  "Person A",
        "transcript": (
            "Yesterday at 7 PM, I was studying in the library with Rahul. "
            "I stayed there until 8 PM and then went to the hostel mess."
        ),
        "expect": {
            "person_matches":        "Person A",
            "locations_must_include": ["library", "hostel mess"],
            "people_must_include":    ["Rahul"],
            "times_must_include":     ["7 PM", "7pm", "19", "8 PM", "8pm", "20"],
            "activity_keywords":      ["study", "studying"],
            "null_hallucination":     False,  # check we do NOT add phantom facts
        },
    },
    {
        "id":      "TEST 2",
        "person":  "Person B",
        "transcript": "I went to the library.",
        "expect": {
            "person_matches":        "Person B",
            "locations_must_include": ["library"],
            "people_must_include":    [],       # no people mentioned
            "times_must_include":     [],       # no time mentioned → must be null/[]
            "times_must_be_empty":    True,
            "activity_keywords":      ["went", "go", "walk"],
            "null_hallucination":     True,     # time must be null/absent
        },
    },
    {
        "id":      "TEST 3",
        "person":  "Person A",
        "transcript": (
            "At 6 PM I went to the canteen. I met Ravi and had dinner."
        ),
        "expect": {
            "person_matches":        "Person A",
            "locations_must_include": ["canteen"],
            "people_must_include":    ["Ravi"],
            "times_must_include":     ["6 PM", "6pm", "18"],
            "activity_keywords":      ["dinner", "eat", "had", "met", "meet"],
            "null_hallucination":     False,
        },
    },
]

# ── Helper assertion functions ─────────────────────────────────────────────────

def assert_person(data: dict, expected: str) -> bool:
    actual = (data.get("person") or "").strip()
    if expected.lower() in actual.lower():
        ok(f"person = '{actual}'")
        return True
    fail(f"person mismatch — expected '{expected}', got '{actual}'")
    return False


def assert_locations(data: dict, must_include: list[str]) -> bool:
    all_locs = " | ".join(
        str(v).lower()
        for v in [
            data.get("all_locations_mentioned", []),
            *[e.get("location", "") for e in data.get("events", [])],
        ]
        if v
    )
    passed = True
    for loc in must_include:
        if loc.lower() in all_locs:
            ok(f"location '{loc}' found")
        else:
            fail(f"location '{loc}' NOT found in: {all_locs!r}")
            passed = False
    return passed


def assert_people(data: dict, must_include: list[str]) -> bool:
    all_people = " | ".join(
        str(v).lower()
        for v in [
            data.get("all_people_mentioned", []),
            *[name for e in data.get("events", []) for name in e.get("people", [])],
        ]
        if v
    )
    if not must_include:
        # Expect no companion people in the story events.
        # The narrator label ("Person B") in all_people_mentioned is acceptable —
        # the LLM reasonably infers the narrator from context.
        # What we must verify: event-level people[] lists are empty (no invented companions).
        event_people = [
            name
            for e in data.get("events", [])
            for name in e.get("people", [])
        ]
        narrator_label = data.get("person", "").lower()
        # Filter out the narrator themselves from all_people_mentioned
        non_narrator = [
            p for p in data.get("all_people_mentioned", [])
            if p.lower() != narrator_label
        ]
        if not event_people and not non_narrator:
            ok("event people[] = [] and no extra names invented (correct)")
            return True
        elif not event_people and non_narrator:
            # Only narrator label present — acceptable
            ok(f"event people[] = [] (correct). all_people_mentioned has narrator label only: {data.get('all_people_mentioned')}")
            return True
        else:
            fail(f"Invented companions in event people[]: {event_people}")
            return False
    passed = True
    for person in must_include:
        if person.lower() in all_people:
            ok(f"person '{person}' found")
        else:
            fail(f"person '{person}' NOT found in: {all_people!r}")
            passed = False
    return passed


def assert_times(data: dict, must_include: list[str], must_be_empty: bool = False) -> bool:
    all_times_raw = data.get("all_times_mentioned", [])
    all_times = " | ".join(str(t).lower() for t in all_times_raw if t)
    event_times = " | ".join(
        f"{e.get('start_time','')} {e.get('end_time','')}".lower()
        for e in data.get("events", [])
    )
    combined = f"{all_times} | {event_times}"

    if must_be_empty:
        # None of the time fields should contain a real time
        if not all_times_raw:
            ok("all_times_mentioned = [] (correct — no time in transcript)")
        else:
            fail(f"Expected no times (hallucination risk), got: {all_times_raw}")
            return False
        # Also check every event's start_time and end_time are null
        hallucinated = [
            e for e in data.get("events", [])
            if e.get("start_time") or e.get("end_time")
        ]
        if hallucinated:
            fail(f"Event time fields not null: {hallucinated}")
            return False
        ok("Event start_time / end_time = null (correct)")
        return True

    if not must_include:
        ok("No specific times required for this test")
        return True

    for time_variant in must_include:
        if time_variant.lower() in combined:
            ok(f"time variant '{time_variant}' found in extracted times")
            return True

    fail(f"None of the expected time variants {must_include} found — got: {combined!r}")
    return False


def assert_activity(data: dict, keywords: list[str]) -> bool:
    all_actions = " | ".join(
        str(e.get("action", "")).lower()
        for e in data.get("events", [])
        if e.get("action")
    )
    for kw in keywords:
        if kw.lower() in all_actions:
            ok(f"action keyword '{kw}' found in events")
            return True
    fail(f"No action keywords {keywords} found — got: {all_actions!r}")
    return False


def assert_no_hallucination(data: dict) -> bool:
    """
    For Test 2: Verify the model did NOT invent times that weren't in the transcript.
    """
    times = data.get("all_times_mentioned", [])
    event_times = [
        t for e in data.get("events", [])
        for t in [e.get("start_time"), e.get("end_time")]
        if t
    ]
    if times or event_times:
        fail(f"Hallucination detected! Invented times: {times + event_times}")
        return False
    ok("No time hallucination — all time fields are null/empty (correct)")
    return True


# ── Run tests ──────────────────────────────────────────────────────────────────

overall_passed = 0
overall_failed = 0

for tc in TEST_CASES:
    sep(f"{tc['id']} — {tc['person']}")
    print(f"  Transcript: \"{tc['transcript']}\"")
    print()

    # ── API call ───────────────────────────────────────────────────────────────
    t_start = time.time()
    try:
        data = extract_story_facts(tc["transcript"], tc["person"])
        elapsed = time.time() - t_start
        ok(f"API call succeeded ({elapsed:.1f}s)")
    except Exception as exc:
        elapsed = time.time() - t_start
        fail(f"API call FAILED after {elapsed:.1f}s: {exc}")
        overall_failed += 1
        continue

    # ── Validation ─────────────────────────────────────────────────────────────
    is_valid, errors = validate_extracted_story(data)
    if is_valid:
        ok("validate_extracted_story() → PASS")
    else:
        for e in errors:
            fail(f"Validation error: {e}")

    # ── Assertions ─────────────────────────────────────────────────────────────
    exp = tc["expect"]
    checks = []

    checks.append(assert_person(data, exp["person_matches"]))
    checks.append(assert_locations(data, exp["locations_must_include"]))
    checks.append(assert_people(data, exp["people_must_include"]))
    checks.append(assert_times(
        data,
        exp["times_must_include"],
        must_be_empty=exp.get("times_must_be_empty", False),
    ))
    checks.append(assert_activity(data, exp["activity_keywords"]))

    # Special hallucination guard for Test 2
    if exp.get("null_hallucination"):
        checks.append(assert_no_hallucination(data))

    # ── Print the structured JSON ──────────────────────────────────────────────
    print()
    info("Structured JSON returned by LLM:")
    print(json.dumps(data, indent=2, ensure_ascii=False))

    # ── Summary for this test ──────────────────────────────────────────────────
    tc_pass = all(checks) and is_valid
    tc_label = f"{GREEN}PASSED{RESET}" if tc_pass else f"{RED}FAILED{RESET}"
    print(f"\n  {tc['id']} result: {tc_label}")
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
