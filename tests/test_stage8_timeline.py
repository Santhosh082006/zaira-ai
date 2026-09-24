import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from services.story_analyzer import validate_extracted_story
from services.story_comparator import validate_comparison

passed = 0
total = 0

def assert_test(condition, name):
    global passed, total
    total += 1
    if condition:
        print(f"  PASS  {name}")
        passed += 1
    else:
        print(f"  FAIL  {name}")

print("==================================================================")
print("  TruthLens AI — Stage 8 Deterministic Schema Tests")
print("==================================================================")

valid_story = {
  "person": "Person A",
  "summary": "Test summary",
  "events": [
    {
      "event_id": "E1",
      "sequence": 1,
      "time": "around 9 AM",
      "time_normalized": "09:00",
      "location": "college gate",
      "people": ["Rahul"],
      "action": "arrived",
      "description": "Person reached the college gate",
      "source_text": "I reached the college gate around 9 AM."
    }
  ],
  "claims": [
    {
      "claim_id": "C1",
      "subject": "conversation with Rahul",
      "attribute": "duration",
      "value": "about 10 minutes",
      "source_text": "I spoke with Rahul for about ten minutes."
    }
  ],
  "all_people_mentioned": ["Rahul"],
  "all_locations_mentioned": ["college gate"],
  "all_times_mentioned": ["around 9 AM"],
  "all_dates_mentioned": [],
  "extraction_confidence": "high"
}

is_valid, errs = validate_extracted_story(valid_story)
assert_test(is_valid, "Valid event and claim extraction passes validation")

minimal_event_story = valid_story.copy()
minimal_event_story["events"] = [
    {
      "event_id": "E1",
      "sequence": 1,
      "description": "Person reached the college gate",
      "source_text": "I reached the college gate around 9 AM."
    }
]
is_valid, errs = validate_extracted_story(minimal_event_story)
assert_test(is_valid, "Event missing optional fields (time, location) passes validation")

bad_event_story = valid_story.copy()
bad_event_story["events"] = [{"event_id": "E1", "sequence": 1}]
is_valid, errs = validate_extracted_story(bad_event_story)
assert_test(not is_valid and "description" in errs[0], "Missing description fails validation")

bad_claim_story = valid_story.copy()
bad_claim_story["claims"] = [{"claim_id": "C1"}]
is_valid, errs = validate_extracted_story(bad_claim_story)
assert_test(not is_valid and "subject" in errs[0], "Missing subject fails validation")


valid_comparison = {
  "overall_status": "discrepancies_found",
  "matches": [],
  "discrepancies": [],
  "missing_information": [],
  "unclear_information": [],
  "timeline_comparison": [
    {
      "event_a": {"event_id": "E1", "description": "Met Rahul", "source_text": "I met Rahul."},
      "event_b": {"event_id": "E1", "description": "Met Rahul", "source_text": "I saw Rahul."},
      "status": "MATCH"
    },
    {
      "event_a": {"event_id": "E2", "description": "Talked 10 min", "source_text": "Talked 10m."},
      "event_b": {"event_id": "E2", "description": "Talked 5 min", "source_text": "Talked 5m."},
      "status": "PARTIAL_MATCH"
    },
    {
      "event_a": None,
      "event_b": {"event_id": "E3", "description": "Left", "source_text": "I left."},
      "status": "MISSING_A"
    },
    {
      "event_a": {"event_id": "E4", "description": "Ate", "source_text": "I ate."},
      "event_b": None,
      "status": "MISSING_B"
    }
  ],
  "claim_comparison": [
    {
      "subject": "conversation",
      "attribute": "duration",
      "person_a": {"value": "10 min", "source_text": "10 min"},
      "person_b": {"value": "5 min", "source_text": "5 min"},
      "status": "CONFLICT"
    },
    {
      "subject": "weather",
      "attribute": "condition",
      "person_a": {"value": "raining", "source_text": "raining"},
      "person_b": None,
      "status": "UNKNOWN"
    }
  ],
  "summary": "Testing summary."
}

is_valid, errs = validate_comparison(valid_comparison)
assert_test(is_valid, "Valid comparison with all statuses passes validation")

bad_comparison = valid_comparison.copy()
bad_comparison["summary"] = "Person A is lying about the time."
is_valid, errs = validate_comparison(bad_comparison)
assert_test(not is_valid and "lying" in str(errs), "Forbidden word 'lying' caught in validation")

malformed_comparison = valid_comparison.copy()
del malformed_comparison["timeline_comparison"]
is_valid, errs = validate_comparison(malformed_comparison)
assert_test(not is_valid and "timeline_comparison" in str(errs), "Missing timeline_comparison array caught")

print("==================================================================")
print(f"  Tests run    : {total}")
print(f"  Passed       : {passed}")
print(f"  Failed       : {total - passed}")
print("==================================================================")

if passed < total:
    sys.exit(1)
