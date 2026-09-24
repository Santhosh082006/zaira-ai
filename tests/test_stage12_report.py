import os
import sys
import unittest
import copy

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from services.report_generator import generate_evidence_report

class TestReportGenerator(unittest.TestCase):
    def setUp(self):
        self.mock_comparison = {
            "overall_status": "discrepancies_found",
            "matches": [
                {"category": "location", "description": "Met at cafe"}
            ],
            "discrepancies": [
                {"category": "time", "description": "Time conflict", "person_a_value": "1 PM", "person_b_value": "2 PM"}
            ],
            "missing_information": [
                {"category": "people", "description": "Alice absent in B", "present_in": "A"}
            ],
            "unclear_information": [
                {"category": "weather", "description": "Vague descriptions"}
            ],
            "timeline_comparison": [
                {
                    "status": "MATCH",
                    "reason": "Both arrived at same time.",
                    "evidence_points": ["Same context"],
                    "event_a": {"source_text": "I arrived at 1"},
                    "event_b": {"source_text": "I got there at 1"}
                },
                {
                    "status": "CONFLICT",
                    "reason": "Different duration.",
                    "evidence_points": ["Conflict context"],
                    "event_a": {"source_text": "stayed 1 hour"},
                    "event_b": {"source_text": "stayed 2 hours"}
                },
                {
                    "status": "MISSING_B",
                    "reason": "Only A mentioned it.",
                    "event_a": {"source_text": "I saw a dog"}
                }
            ],
            "claim_comparison": [
                {
                    "status": "PARTIAL_MATCH",
                    "subject": "Duration",
                    "attribute": "length",
                    "person_a": {"source_text": "A long time"},
                    "person_b": {"source_text": "hours"}
                }
            ]
        }
        self.mock_story_a = {"person": "Alice"}
        self.mock_story_b = {"person": "Bob"}
        self.mock_speech_a = {"duration_seconds": 10.5, "speaking_rate_wpm": 120, "reliability_flag": "good"}
        self.mock_visual_b = {"face_detected": True, "blink_count": 5}

    def test_complete_comparison(self):
        pdf_bytes = generate_evidence_report(
            comparison_result=self.mock_comparison,
            story_a=self.mock_story_a,
            story_b=self.mock_story_b,
            speech_a=self.mock_speech_a,
            visual_b=self.mock_visual_b
        )
        self.assertIsInstance(pdf_bytes, bytes)
        self.assertGreater(len(pdf_bytes), 1000) # PDF should have substantial size

    def test_empty_events_and_claims(self):
        empty_comp = copy.deepcopy(self.mock_comparison)
        empty_comp["timeline_comparison"] = []
        empty_comp["claim_comparison"] = []
        pdf_bytes = generate_evidence_report(comparison_result=empty_comp)
        self.assertIsInstance(pdf_bytes, bytes)

    def test_missing_speech_and_visual(self):
        pdf_bytes = generate_evidence_report(
            comparison_result=self.mock_comparison
            # No speech/visual args passed
        )
        self.assertIsInstance(pdf_bytes, bytes)

    def test_missing_source_text(self):
        no_source_comp = copy.deepcopy(self.mock_comparison)
        no_source_comp["timeline_comparison"][0]["event_a"].pop("source_text")
        pdf_bytes = generate_evidence_report(comparison_result=no_source_comp)
        self.assertIsInstance(pdf_bytes, bytes)

    def test_multi_page(self):
        # Add many events to force multi-page
        large_comp = copy.deepcopy(self.mock_comparison)
        large_comp["timeline_comparison"] = [large_comp["timeline_comparison"][0]] * 50
        pdf_bytes = generate_evidence_report(comparison_result=large_comp)
        self.assertIsInstance(pdf_bytes, bytes)

    def test_forbidden_language(self):
        pdf_bytes = generate_evidence_report(comparison_result=self.mock_comparison)
        pdf_text = pdf_bytes.decode('latin-1', 'ignore').lower()
        forbidden = ["lying", "truth score", "deception probability", "credibility score", "truthfulness percentage"]
        # "lie" and "honest" might accidentally be substrings in PDF binary overhead, but let's check exact strings
        for word in forbidden:
            self.assertNotIn(word, pdf_text)
            
    def test_input_not_modified(self):
        original = copy.deepcopy(self.mock_comparison)
        generate_evidence_report(comparison_result=self.mock_comparison)
        self.assertEqual(self.mock_comparison, original)

if __name__ == "__main__":
    unittest.main()
