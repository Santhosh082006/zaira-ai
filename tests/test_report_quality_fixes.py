"""
tests/test_report_quality_fixes.py
Comprehensive regression tests for TruthLens AI report quality and data integrity fixes:
- Issue 1: Null metric formatting ("Nones" bug elimination)
- Issue 2: Accurate status flag and coverage scoring (never 100% on missing/all-null data)
- Issue 3: Structural declining of missing categories ("Insufficient Data" and "N/A")
- Issue 4: Head movement normalization (movements per minute + 15-35/min typical range)
- Issue 5: Decoupled category improvement recommendations (no duplicate text)
- Issue 6: Timeline event time key resolution (never "None - Location")
"""

import os
import sys
import re
import zlib
import unittest
import streamlit as st

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from services.report_generator import (
    _format_metric,
    generate_performance_report,
    generate_evidence_report
)
from services.story_analyzer import (
    evaluate_individual_account,
    _enforce_data_integrity,
    _deterministic_evaluation
)
from services.visual_features import extract_visual_features
from app import calculate_analysis_coverage


def _extract_pdf_text(pdf_bytes: bytes) -> str:
    """Extract raw decompressed text streams from an FPDF-generated PDF byte array."""
    streams = re.findall(rb'stream[\r\n]+(.*?)[\r\n]+endstream', pdf_bytes, re.DOTALL)
    all_text = []
    for s in streams:
        try:
            decomp = zlib.decompress(s).decode('latin-1', 'replace')
            all_text.append(decomp)
        except Exception:
            all_text.append(s.decode('latin-1', 'replace'))
    return "\n".join(all_text)


class TestReportQualityFixes(unittest.TestCase):

    # ── Issue 1: Null metric formatting ("Nones" bug) ───────────────────────────
    def test_format_metric_helper(self):
        self.assertEqual(_format_metric(None, "s"), "N/A")
        self.assertEqual(_format_metric(None, " WPM"), "N/A")
        self.assertEqual(_format_metric("", " Hz"), "N/A")
        self.assertEqual(_format_metric("N/A", " dB"), "N/A")
        self.assertEqual(_format_metric(12.345, "s", ".1f"), "12.3s")
        self.assertEqual(_format_metric(140, " WPM", ".0f"), "140 WPM")
        self.assertEqual(_format_metric(0, "s"), "0s")

    def test_performance_report_no_nones(self):
        null_speech = {
            "duration_seconds": None,
            "word_count": 18,
            "speaking_rate_wpm": None,
            "pause_count": None,
            "total_pause_duration_sec": None,
            "filler_word_count": 0,
            "pitch_mean_hz": None,
            "pitch_variation_hz": None,
            "energy_mean_db": None,
            "reliability_flag": "audio_missing"
        }
        visual = {
            "face_detected": True,
            "face_presence_ratio": 0.95,
            "head_movement_count": 165,
            "blink_count": 8,
            "duration_seconds": 90.0,
            "head_movement_rate_per_min": 110.0,
            "tracking_reliability": "good"
        }
        story = {
            "summary": "Sample narrative",
            "events": [{"time": None, "location": "University of Rochester", "description": "Classes attended"}]
        }
        eval_data = {
            "speaking_style": {"score": "Insufficient Data", "assessment": "No audio", "evidence_observation": "Acoustic missing", "what_went_well": "N/A", "what_needs_improvement": "N/A", "practical_recommendation": "Record audio"},
            "confidence_indicators": {"score": 75, "assessment": "Steady composure", "evidence_observation": "Observed", "what_went_well": "Clear delivery", "what_needs_improvement": "Limit filler pauses", "practical_recommendation": "Practice"},
            "body_language": {"score": 70, "assessment": "Good posture", "evidence_observation": "Tracking active", "what_went_well": "Composed", "what_needs_improvement": "Reduce head shifts", "practical_recommendation": "Center camera"},
            "engagement": {"score": 75, "assessment": "Camera eye contact maintained", "evidence_observation": "Face visible", "what_went_well": "Eye contact", "what_needs_improvement": "Maintain gaze", "practical_recommendation": "Eye level"},
            "story_quality": {"score": 70, "assessment": "Chronological structure", "evidence_observation": "Factual", "what_went_well": "Narrative flow", "what_needs_improvement": "Add timestamps", "practical_recommendation": "Structure events"}
        }

        pdf_bytes = generate_performance_report(
            person_label="Test User",
            story=story,
            speech=null_speech,
            visual=visual,
            eval_data=eval_data,
            coverage_score=75,
            coverage_breakdown=["Speech Analysis ❌ Failed/Unmeasured"]
        )

        extracted = _extract_pdf_text(pdf_bytes)

        # Must not contain "Nones", "None WPM", "None Hz" or "None dB"
        self.assertNotIn("Nones", extracted)
        self.assertNotIn("None WPM", extracted)
        self.assertNotIn("None Hz", extracted)
        self.assertNotIn("None dB", extracted)
        # Must not contain "Strength: N/A" or "Improvement Area: N/A"
        self.assertNotIn("Strength: N/A", extracted)
        self.assertNotIn("Improvement Area: N/A", extracted)

    # ── Issue 2: Accurate status flag and coverage scoring ──────────────────────
    def test_coverage_fails_on_null_speech(self):
        st.session_state["transcript_test2"] = "I was born at Strong Memorial Hospital in Rochester, New York."
        st.session_state["audio_path_test2"] = "test.wav"
        st.session_state["video_path_test2"] = "test.mp4"
        st.session_state["speech_features_test2"] = {
            "duration_seconds": None,
            "word_count": 10,
            "speaking_rate_wpm": None,
            "reliability_flag": "audio_missing"
        }
        st.session_state["visual_features_test2"] = {
            "face_detected": True,
            "face_presence_ratio": 0.95,
            "head_movement_count": 20,
            "tracking_reliability": "good"
        }
        st.session_state["story_data_test2"] = {
            "events": [{"time": "2020", "location": "Rochester", "description": "Born"}],
            "claims": [{"subject": "Person", "value": "Born in Rochester"}]
        }
        st.session_state["evaluation_data_test2"] = {
            "speaking_style": {"score": "Insufficient Data"},
            "confidence_indicators": {"score": 70},
            "body_language": {"score": 75},
            "engagement": {"score": 75},
            "story_quality": {"score": 75}
        }

        score, breakdown = calculate_analysis_coverage("test2")

        # Must not be 100/100
        self.assertLess(score, 100)
        # Speech analysis must show Failed/Unmeasured, NOT Complete
        speech_item = next((b for b in breakdown if "Speech Analysis" in b), "")
        self.assertIn("Failed/Unmeasured", speech_item)
        self.assertNotIn("✅ Complete", speech_item)

    # ── Issue 3: Structural declining of missing categories ─────────────────────
    def test_missing_audio_declines_speaking_style(self):
        speech = {
            "duration_seconds": None,
            "word_count": 18,
            "speaking_rate_wpm": None,
            "reliability_flag": "audio_missing"
        }
        visual = {
            "face_detected": True,
            "face_presence_ratio": 0.95,
            "head_movement_count": 20,
            "head_movement_rate_per_min": 25.0,
            "tracking_reliability": "good"
        }
        transcript = "I was born at Strong Memorial Hospital in Rochester, New York."
        story = {"events": [{"time": None, "location": "Rochester", "description": "Born"}]}

        res = evaluate_individual_account("Performer", transcript, story, speech, visual)

        self.assertEqual(res["speaking_style"]["score"], "Insufficient Data")
        self.assertEqual(res["speaking_style"]["what_went_well"], "N/A")
        self.assertEqual(res["speaking_style"]["what_needs_improvement"], "N/A")

    def test_missing_visual_declines_body_and_engagement(self):
        speech = {
            "duration_seconds": 60.0,
            "word_count": 130,
            "speaking_rate_wpm": 130.0,
            "pause_count": 2,
            "total_pause_duration_sec": 3.0,
            "filler_word_count": 1,
            "reliability_flag": "good"
        }
        visual = {
            "face_detected": False,
            "face_presence_ratio": 0.0,
            "head_movement_count": None,
            "tracking_reliability": "no_face_found"
        }
        transcript = "I was born at Strong Memorial Hospital in Rochester, New York."
        story = {"events": [{"time": None, "location": "Rochester", "description": "Born"}]}

        res = evaluate_individual_account("Performer", transcript, story, speech, visual)

        self.assertEqual(res["body_language"]["score"], "Insufficient Data")
        self.assertEqual(res["body_language"]["what_went_well"], "N/A")
        self.assertEqual(res["body_language"]["what_needs_improvement"], "N/A")
        self.assertEqual(res["engagement"]["score"], "Insufficient Data")
        self.assertEqual(res["engagement"]["what_went_well"], "N/A")
        self.assertEqual(res["engagement"]["what_needs_improvement"], "N/A")

    def test_both_missing_declines_confidence_indicators(self):
        speech = {"duration_seconds": None, "reliability_flag": "audio_missing"}
        visual = {"face_detected": False, "tracking_reliability": "video_missing"}
        transcript = "I was born at Strong Memorial Hospital in Rochester, New York."
        story = {"events": [{"time": None, "location": "Rochester", "description": "Born"}]}

        res = evaluate_individual_account("Performer", transcript, story, speech, visual)

        self.assertEqual(res["confidence_indicators"]["score"], "Insufficient Data")
        self.assertEqual(res["confidence_indicators"]["what_went_well"], "N/A")
        self.assertEqual(res["confidence_indicators"]["what_needs_improvement"], "N/A")

    # ── Issue 4: Head movement normalization & baseline ────────────────────────
    def test_head_movement_rate_in_report_and_observation(self):
        visual = {
            "face_detected": True,
            "face_presence_ratio": 0.95,
            "head_movement_count": 165,
            "head_movement_rate_per_min": 110.0,
            "head_movement_typical_range": "15-35/min",
            "duration_seconds": 90.0,
            "blink_count": 8,
            "tracking_reliability": "good"
        }
        pdf_bytes = generate_performance_report(
            person_label="Test Performer",
            visual=visual
        )
        extracted = _extract_pdf_text(pdf_bytes)

        # Check rate and typical range presence in report
        self.assertIn("110.0/min", extracted)
        self.assertIn("typical range: 15-35/min", extracted)

    # ── Issue 5: Decoupled category improvement recommendations ────────────────
    def test_confidence_and_story_quality_distinct_improvement(self):
        eval_data = {
            "confidence_indicators": {
                "score": 75,
                "what_needs_improvement": "claims lack supporting evidence and need proof."
            },
            "story_quality": {
                "score": 70,
                "what_needs_improvement": "claims lack supporting evidence and need proof."
            }
        }
        enforced = _enforce_data_integrity(
            eval_data=eval_data,
            has_valid_speech=True,
            has_valid_visual=True,
            has_valid_transcript=True,
            has_valid_story=True
        )

        ci_imp = enforced["confidence_indicators"]["what_needs_improvement"]
        sq_imp = enforced["story_quality"]["what_needs_improvement"]

        # Must NOT be identical
        self.assertNotEqual(ci_imp, sq_imp)
        # Story quality must focus on narrative chronology
        self.assertTrue(
            "chronology" in sq_imp.lower() or "timestamps" in sq_imp.lower() or "transition" in sq_imp.lower()
        )

    # ── Issue 6: Timeline event time key resolution ────────────────────────────
    def test_timeline_event_with_none_time_renders_cleanly(self):
        story = {
            "events": [
                {
                    "time": None,
                    "time_or_relative_time": None,
                    "location": "University of Rochester",
                    "description": "Enrolled in undergraduate degree."
                }
            ]
        }
        pdf_bytes = generate_performance_report(
            person_label="Test Performer",
            story=story
        )
        extracted = _extract_pdf_text(pdf_bytes)

        # Must NOT contain "None - University of Rochester"
        self.assertNotIn("None - University of Rochester", extracted)
        self.assertIn("Time unstated - University of Rochester", extracted)


if __name__ == "__main__":
    unittest.main()
