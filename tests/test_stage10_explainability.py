import os
import sys
import unittest

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from services.story_comparator import _post_process_comparisons

class TestExplainability(unittest.TestCase):
    def test_explainability_injection(self):
        # Create a mock comparison object with all statuses
        mock_data = {
            "claim_comparison": [
                {
                    "status": "MATCH",
                    "subject": "Time",
                    "attribute": "Start",
                    "person_a": {"value": "9 AM", "source_text": "I started at 9 AM."},
                    "person_b": {"value": "9 AM", "source_text": "It was 9 AM."}
                },
                {
                    "status": "CONFLICT",
                    "subject": "Duration",
                    "attribute": "Length",
                    "person_a": {"value": "10 mins", "source_text": "10 mins."},
                    "person_b": {"value": "5 mins", "source_text": "5 mins."}
                },
                {
                    "status": "PARTIAL_MATCH",
                    "subject": "Location",
                    "attribute": "Place",
                    "person_a": {"value": "library", "source_text": "library"},
                    "person_b": {"value": "main library", "source_text": "main library"}
                },
                {
                    "status": "MISSING_B",
                    "subject": "Color",
                    "attribute": "Shirt",
                    "person_a": {"value": "blue", "source_text": "blue shirt"},
                    "person_b": None
                },
                {
                    "status": "MISSING_A",
                    "subject": "Food",
                    "attribute": "Meal",
                    "person_a": None,
                    "person_b": {"value": "pizza", "source_text": "had pizza"}
                },
                {
                    "status": "UNKNOWN",
                    "subject": "Weather",
                    "attribute": "Rain",
                    "person_a": None,
                    "person_b": None
                }
            ],
            "timeline_comparison": [
                {
                    "status": "MATCH",
                    "event_a": {"description": "met rahul", "location": "canteen", "time": "9 AM"},
                    "event_b": {"description": "met rahul", "location": "canteen", "time": "9 AM"}
                },
                {
                    "status": "CONFLICT",
                    "event_a": {"description": "went home", "location": "library"},
                    "event_b": {"description": "went to store", "location": "store"}
                },
                {
                    "status": "CONFLICT",
                    "event_a": {"description": "arrived", "time": "9 AM"},
                    "event_b": {"description": "arrived", "time": "10 AM"}
                },
                {
                    "status": "CONFLICT",
                    "event_a": {"description": "met Rahul"},
                    "event_b": {"description": "met Arjun"}
                },
                {
                    "status": "MISSING_B",
                    "event_a": {"description": "studied", "source_text": "studied"},
                    "event_b": None
                },
                {
                    "status": "MISSING_A",
                    "event_a": None,
                    "event_b": {"description": "slept", "source_text": "slept"}
                }
            ]
        }
        
        result = _post_process_comparisons(mock_data)
        
        claims = result["claim_comparison"]
        events = result["timeline_comparison"]
        
        # Helper to find claim by subject
        def get_claim(subj):
            for c in claims:
                if c.get("subject") == subj: return c
            return None
            
        def get_event(desc):
            for e in events:
                if e.get("event_a") and e["event_a"].get("description") == desc: return e
                if e.get("event_b") and e["event_b"].get("description") == desc: return e
            return None
            
        # 1. MATCH Claim
        c_match = get_claim("Time")
        self.assertIn("Both accounts provide equivalent information regarding Time (Start)", c_match["reason"])
        
        # 2. CONFLICT Claim (Duration)
        c_conflict = get_claim("Duration")
        self.assertIn("Person A reports 10 mins, while Person B reports 5 mins", c_conflict["reason"])
        self.assertIn("Different values: 10 mins vs 5 mins", str(c_conflict["evidence_points"]))
        
        # 3. PARTIAL_MATCH Claim
        c_partial = get_claim("Location")
        self.assertIn("Person A reports library, while Person B reports main library", c_partial["reason"])
        
        # 4. MISSING_B Claim
        c_mb = get_claim("Color")
        self.assertIn("Person A provides this information, but Person B does not mention it", c_mb["reason"])
        
        # 5. MISSING_A Claim
        c_ma = get_claim("Food")
        self.assertIn("Person B provides this information, but Person A does not mention it", c_ma["reason"])
        
        # 6. Events
        e_match = get_event("met rahul")
        self.assertIn("Equivalent location", e_match["evidence_points"])
        
        e_loc = get_event("went home")
        self.assertIn("Person A places the event at library, while Person B places it at store.", e_loc["reason"])
        
        e_time = get_event("arrived")
        self.assertIn("Person A reports approximately 9 AM, while Person B reports approximately 10 AM.", e_time["reason"])
        
        e_desc = get_event("met Rahul")
        self.assertIn("Person A describes met Rahul, while Person B describes met Arjun.", e_desc["reason"])
        
        # No forbidden language test (the _post_process_comparisons does not generate lying/deceptive)
        all_text = str(result).lower()
        self.assertNotIn("lying", all_text)
        self.assertNotIn("deceptive", all_text)
        self.assertNotIn("truthful", all_text)

if __name__ == "__main__":
    unittest.main()
