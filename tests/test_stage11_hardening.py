import os
import sys
import unittest

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from services.story_analyzer import _parse_json_response, validate_extracted_story, extract_story_facts
from services.story_comparator import _parse_comparison_response, validate_comparison
from services.speech_features import extract_speech_features
from services.visual_features import extract_visual_features

class TestHardening(unittest.TestCase):
    def test_json_parsing_malformed(self):
        malformed = "```json\n { \"person\": \"A\", \n```"
        with self.assertRaises(RuntimeError) as context:
            _parse_json_response(malformed, "Person A")
        self.assertIn("could not be parsed as JSON", str(context.exception))
        
    def test_validate_extracted_story_empty_arrays(self):
        # Empty arrays should be completely valid
        data = {
            "person": "A",
            "summary": "Sum",
            "extraction_confidence": "high",
            "events": [],
            "claims": [],
            "all_people_mentioned": [],
            "all_locations_mentioned": [],
            "all_times_mentioned": [],
            "all_dates_mentioned": []
        }
        is_valid, errs = validate_extracted_story(data)
        self.assertTrue(is_valid)
        self.assertEqual(len(errs), 0)
        
    def test_validate_extracted_story_missing_fields(self):
        data = {
            "person": "A",
            "events": []
        }
        is_valid, errs = validate_extracted_story(data)
        self.assertFalse(is_valid)
        self.assertTrue(any("Missing required field" in e for e in errs))
        
    def test_validate_comparison_empty(self):
        data = {
            "overall_status": "consistent",
            "matches": [],
            "discrepancies": [],
            "missing_information": [],
            "unclear_information": [],
            "timeline_comparison": [],
            "claim_comparison": [],
            "summary": "All good"
        }
        is_valid, errs = validate_comparison(data)
        self.assertTrue(is_valid)
        self.assertEqual(len(errs), 0)
        
    def test_empty_transcript(self):
        with self.assertRaises(ValueError):
            extract_story_facts("", "Person A")
        with self.assertRaises(ValueError):
            extract_story_facts("   \n ", "Person A")
            
    def test_speech_missing_audio(self):
        feats = extract_speech_features("does_not_exist.wav", "Hello")
        self.assertEqual(feats["reliability_flag"], "audio_missing")
        
    def test_visual_missing_video(self):
        v_feats = extract_visual_features("does_not_exist.mp4")
        self.assertEqual(v_feats["tracking_reliability"], "video_missing")

if __name__ == "__main__":
    unittest.main()
