"""
scratch/verify_ui_reorder.py
─────────────────────────────────────────────────────────────────────────────
Comprehensive UI/UX Verification Script for TruthLens AI:
Verifies the exact rendered order and section naming of the Individual Performance Assessment:

1. 📊 Communication Performance Assessment (First visible assessment section)
2. Five Performance Categories:
   - 🧠 Confidence Indicators
   - 🧍 Body Language & Posture
   - 🗣️ Speaking Style & Fluency
   - 👁️ Engagement & Camera Presence
   - ⭐ Story Quality & Structure
3. 📋 Overall Performance Summary
   - ✅ Key Strengths
   - ⚠️ Priority Improvement Opportunities
4. 🔍 Analysis Details
   - 📊 Analysis Coverage
   - 📄 Spoken Transcript
   - 🗣️ Observable Speech Signals
   - 👁️ Observable Visual Signals
5. PDF Report Export

CRITICAL CHECKS:
- "🎯 Multimodal Performance Breakdown" MUST NOT appear anywhere.
- "📊 Performance Assessment: Individual Performer" MUST NOT appear anywhere.
"""

import sys
import os
import unittest

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from streamlit.testing.v1 import AppTest
from processors.context_engine.weighting import get_context_profile, CONTEXT_JOB_INTERVIEW
from analytical_engine.evaluator import compute_deterministic_scores
from core.constants import VIDEO_DIR


class TestReportUIReorder(unittest.TestCase):

    def setUp(self):
        self.profile = get_context_profile(CONTEXT_JOB_INTERVIEW)
        self.speech = {
            "duration_seconds": 22.0,
            "word_count": 48,
            "speaking_rate_wpm": 130.0,
            "pause_count": 2,
            "total_pause_duration_sec": 1.5,
            "filler_word_count": 1,
            "reliability_flag": "good"
        }
        self.visual = {
            "face_detected": True,
            "face_presence_ratio": 0.98,
            "head_movement_count": 8,
            "head_movement_rate_per_min": 21.8,
            "blink_count": 6,
            "duration_seconds": 22.0,
            "tracking_reliability": "good"
        }
        self.transcript = "I arrived at the headquarters at nine AM and presented our quarterly roadmap to the executive committee."
        self.story = {
            "person": "Individual Performer",
            "summary": "Presented roadmap at headquarters.",
            "events": [
                {"event_id": "E1", "sequence": 1, "time": "9:00 AM", "location": "Headquarters", "description": "Arrived at headquarters", "source_text": self.transcript}
            ],
            "claims": [
                {"claim_id": "C1", "subject": "Roadmap", "attribute": "presented", "value": "Quarterly plan", "source_text": self.transcript}
            ],
            "all_locations_mentioned": ["Headquarters"],
            "all_people_mentioned": ["executive committee"]
        }
        self.eval_data = compute_deterministic_scores(
            person_name="Individual Performer",
            transcript=self.transcript,
            story_data=self.story,
            speech_feats=self.speech,
            visual_feats=self.visual,
            profile=self.profile
        )

    def test_apptest_individual_video_rendered_order(self):
        """Use Streamlit AppTest to verify actual rendered order in Individual Video Analysis."""
        at = AppTest.from_file(os.path.join(ROOT_DIR, "app.py"), default_timeout=30)
        at.run()

        # Switch to Individual Video Analysis
        at.sidebar.radio[0].set_value("📁 Individual Video Analysis").run()

        # Set up analyzed session state for "upload"
        person_id = "upload"
        at.session_state[f"video_path_{person_id}"] = os.path.join(VIDEO_DIR, "test_video_a.mp4")
        at.session_state[f"transcript_{person_id}"] = self.transcript
        at.session_state[f"speech_features_{person_id}"] = self.speech
        at.session_state[f"visual_features_{person_id}"] = self.visual
        at.session_state[f"story_data_{person_id}"] = self.story
        at.session_state[f"evaluation_data_{person_id}"] = self.eval_data
        at.run()

        # Collect all markdown, header, subheader text in order of appearance
        all_elements = []
        for el in at.main:
            # Check type of element
            el_type = type(el).__name__
            val = getattr(el, "value", None)
            label = getattr(el, "label", None)
            text = str(val or label or "")
            if text:
                all_elements.append((el_type, text))

        full_page_text = "\n".join([f"[{t}] {txt}" for t, txt in all_elements])

        # ── 1. Old forbidden labels check ─────────────────────────────────────
        self.assertNotIn(
            "Multimodal Performance Breakdown",
            full_page_text,
            "Old label 'Multimodal Performance Breakdown' MUST NOT appear!"
        )
        self.assertNotIn(
            "Performance Assessment: Individual Performer",
            full_page_text,
            "Old label 'Performance Assessment: Individual Performer' MUST NOT appear!"
        )
        self.assertNotIn(
            "Performance Assessment: Live Performer",
            full_page_text,
            "Old label 'Performance Assessment: Live Performer' MUST NOT appear!"
        )

        # ── 2. New required section headers presence ──────────────────────────
        self.assertIn("Communication Performance Assessment", full_page_text)
        self.assertIn("Overall Communication Score", full_page_text)
        self.assertIn("Confidence Indicators", full_page_text)
        self.assertIn("Body Language & Posture", full_page_text)
        self.assertIn("Speaking Style & Fluency", full_page_text)
        self.assertIn("Engagement & Camera Presence", full_page_text)
        self.assertIn("Story Quality & Structure", full_page_text)
        self.assertIn("Overall Performance Summary", full_page_text)
        self.assertIn("Analysis Details", full_page_text)
        self.assertIn("Analysis Coverage", full_page_text)
        self.assertIn("Spoken Transcript", full_page_text)
        self.assertIn("Observable Speech Signals", full_page_text)
        self.assertIn("Observable Visual Signals", full_page_text)

        # ── 3. Exact Sequential Ordering Verification ────────────────────────
        pos_assessment_header = full_page_text.index("Communication Performance Assessment")
        pos_overall_score = full_page_text.index("Overall Communication Score")
        pos_confidence = full_page_text.index("Confidence Indicators")
        pos_body_language = full_page_text.index("Body Language & Posture")
        pos_speaking = full_page_text.index("Speaking Style & Fluency")
        pos_engagement = full_page_text.index("Engagement & Camera Presence")
        pos_story = full_page_text.index("Story Quality & Structure")
        pos_overall_summary = full_page_text.index("Overall Performance Summary")
        pos_analysis_details = full_page_text.index("Analysis Details")
        pos_coverage = full_page_text.index("Analysis Coverage")
        pos_transcript = full_page_text.index("Spoken Transcript")
        pos_speech_signals = full_page_text.index("Observable Speech Signals")
        pos_visual_signals = full_page_text.index("Observable Visual Signals")

        # Verify ordering:
        # Assessment Header < Overall Score < 5 Categories < Overall Summary < Analysis Details < Coverage & Transcript & Signals
        self.assertLess(pos_assessment_header, pos_overall_score, "Assessment Header must come before Overall Communication Score")
        self.assertLess(pos_overall_score, pos_confidence, "Overall Communication Score must come before Confidence Indicators")
        self.assertLess(pos_confidence, pos_body_language, "Confidence Indicators must come before Body Language")
        self.assertLess(pos_body_language, pos_speaking, "Body Language must come before Speaking Style")
        self.assertLess(pos_speaking, pos_engagement, "Speaking Style must come before Engagement")
        self.assertLess(pos_engagement, pos_story, "Engagement must come before Story Quality")
        self.assertLess(pos_story, pos_overall_summary, "Story Quality must come before Overall Summary")
        self.assertLess(pos_overall_summary, pos_analysis_details, "Overall Summary must come before Analysis Details")
        self.assertLess(pos_analysis_details, pos_coverage, "Analysis Details must come before Analysis Coverage")
        self.assertLess(pos_analysis_details, pos_transcript, "Analysis Details must come before Spoken Transcript")
        self.assertLess(pos_analysis_details, pos_speech_signals, "Analysis Details must come before Speech Signals")
        self.assertLess(pos_analysis_details, pos_visual_signals, "Analysis Details must come before Visual Signals")

        print("\n" + "=" * 80)
        print("VERIFICATION SUCCESSFUL (INDIVIDUAL VIDEO): EXACT ORDER VALIDATED")
        print("=" * 80)
        print(f"1. 📊 Communication Performance Assessment (Index: {pos_assessment_header})")
        print(f"   ⭐ Overall Communication Score         (Index: {pos_overall_score})")
        print(f"2.    🧠 Confidence Indicators            (Index: {pos_confidence})")
        print(f"      🧍 Body Language & Posture          (Index: {pos_body_language})")
        print(f"      🗣️ Speaking Style & Fluency          (Index: {pos_speaking})")
        print(f"      👁️ Engagement & Camera Presence     (Index: {pos_engagement})")
        print(f"      ⭐ Story Quality & Structure        (Index: {pos_story})")
        print(f"3. 📋 Overall Performance Summary         (Index: {pos_overall_summary})")
        print(f"4. 🔍 Analysis Details                    (Index: {pos_analysis_details})")
        print(f"      📊 Analysis Coverage                (Index: {pos_coverage})")
        print(f"      📄 Spoken Transcript                (Index: {pos_transcript})")
        print(f"      🗣️ Observable Speech Signals        (Index: {pos_speech_signals})")
        print(f"      👁️ Observable Visual Signals        (Index: {pos_visual_signals})")
        print("=" * 80)

    def test_apptest_live_camera_rendered_order(self):
        """Use Streamlit AppTest to verify actual rendered order in Live Camera Recording."""
        at = AppTest.from_file(os.path.join(ROOT_DIR, "app.py"), default_timeout=30)
        at.run()

        # By default, primary nav is "🎥 Live Camera Recording"
        person_id = "live"
        at.session_state[f"video_path_{person_id}"] = os.path.join(VIDEO_DIR, "test_video_a.mp4")
        at.session_state[f"transcript_{person_id}"] = self.transcript
        at.session_state[f"speech_features_{person_id}"] = self.speech
        at.session_state[f"visual_features_{person_id}"] = self.visual
        at.session_state[f"story_data_{person_id}"] = self.story
        at.session_state[f"evaluation_data_{person_id}"] = self.eval_data
        at.run()

        all_elements = []
        for el in at.main:
            el_type = type(el).__name__
            val = getattr(el, "value", None)
            label = getattr(el, "label", None)
            text = str(val or label or "")
            if text:
                all_elements.append((el_type, text))

        full_page_text = "\n".join([f"[{t}] {txt}" for t, txt in all_elements])

        self.assertNotIn("Multimodal Performance Breakdown", full_page_text)
        self.assertNotIn("Performance Assessment: Live Performer", full_page_text)
        self.assertIn("Communication Performance Assessment", full_page_text)
        self.assertIn("Overall Communication Score", full_page_text)

        pos_assessment_header = full_page_text.index("Communication Performance Assessment")
        pos_overall_score = full_page_text.index("Overall Communication Score")
        pos_confidence = full_page_text.index("Confidence Indicators")
        pos_overall_summary = full_page_text.index("Overall Performance Summary")
        pos_analysis_details = full_page_text.index("Analysis Details")
        pos_coverage = full_page_text.index("Analysis Coverage")

        self.assertLess(pos_assessment_header, pos_overall_score)
        self.assertLess(pos_overall_score, pos_confidence)
        self.assertLess(pos_confidence, pos_overall_summary)
        self.assertLess(pos_overall_summary, pos_analysis_details)
        self.assertLess(pos_analysis_details, pos_coverage)

        print("\n" + "=" * 80)
        print("VERIFICATION SUCCESSFUL (LIVE CAMERA): EXACT ORDER VALIDATED")
        print("=" * 80)

    def test_apptest_compare_videos_rendered_order(self):
        """Use Streamlit AppTest to verify individual assessment inside Compare & Assess expander."""
        at = AppTest.from_file(os.path.join(ROOT_DIR, "app.py"), default_timeout=30)
        at.run()

        # Switch to Compare & Assess
        at.sidebar.radio[0].set_value("⚖️ Compare & Assess").run()

        # Set up analyzed session state for "a"
        at.session_state["video_path_a"] = os.path.join(VIDEO_DIR, "test_video_a.mp4")
        at.session_state["transcript_a"] = self.transcript
        at.session_state["speech_features_a"] = self.speech
        at.session_state["visual_features_a"] = self.visual
        at.session_state["story_data_a"] = self.story
        at.session_state["evaluation_data_a"] = self.eval_data
        at.run()

        all_elements = []
        for el in at.main:
            el_type = type(el).__name__
            val = getattr(el, "value", None)
            label = getattr(el, "label", None)
            text = str(val or label or "")
            if text:
                all_elements.append((el_type, text))

        full_page_text = "\n".join([f"[{t}] {txt}" for t, txt in all_elements])

        self.assertNotIn("Multimodal Performance Breakdown", full_page_text)
        self.assertNotIn("Performance Assessment: Video A", full_page_text)
        self.assertIn("Communication Performance Assessment", full_page_text)
        self.assertIn("Overall Communication Score", full_page_text)

        pos_assessment_header = full_page_text.index("Communication Performance Assessment")
        pos_overall_score = full_page_text.index("Overall Communication Score")
        pos_confidence = full_page_text.index("Confidence Indicators")
        pos_overall_summary = full_page_text.index("Overall Performance Summary")
        pos_analysis_details = full_page_text.index("Analysis Details")
        pos_coverage = full_page_text.index("Analysis Coverage")

        self.assertLess(pos_assessment_header, pos_overall_score)
        self.assertLess(pos_overall_score, pos_confidence)
        self.assertLess(pos_confidence, pos_overall_summary)
        self.assertLess(pos_overall_summary, pos_analysis_details)
        self.assertLess(pos_analysis_details, pos_coverage)

        print("\n" + "=" * 80)
        print("VERIFICATION SUCCESSFUL (COMPARE & ASSESS INDIVIDUAL): EXACT ORDER VALIDATED")
        print("=" * 80)

    def test_overall_communication_score_mathematics(self):
        """Verify mathematical calculation, profile weighting, and proportional normalization."""
        from analytical_engine.evaluator import calculate_overall_communication_score
        from core.constants import (
            CAT_SPEAKING_STYLE,
            CAT_CONFIDENCE,
            CAT_STORY_QUALITY,
            CAT_BODY_LANGUAGE,
            CAT_ENGAGEMENT,
            INSUFFICIENT_DATA,
            CONTEXT_JOB_INTERVIEW,
            CONTEXT_VC_PITCH,
            CONTEXT_CASUAL_MEETING,
        )

        # 1. Job Interview weighting:
        # Speaking (0.25), Confidence (0.25), Story (0.25), Body Language (0.15), Engagement (0.10)
        eval_sample = {
            CAT_SPEAKING_STYLE: {"score": 80, "what_went_well": "Fluent rate"},
            CAT_CONFIDENCE: {"score": 80, "what_went_well": "Composed"},
            CAT_STORY_QUALITY: {"score": 80, "what_went_well": "Detailed events"},
            CAT_BODY_LANGUAGE: {"score": 60, "what_needs_improvement": "Frequent head tilt"},
            CAT_ENGAGEMENT: {"score": 60, "what_needs_improvement": "Camera gaze"}
        }
        # Expected: 80*0.25 + 80*0.25 + 80*0.25 + 60*0.15 + 60*0.10 = 20 + 20 + 20 + 9 + 6 = 75
        score, text = calculate_overall_communication_score(eval_sample, CONTEXT_JOB_INTERVIEW)
        self.assertEqual(score, 75)
        self.assertIn("clear and composed", text)
        self.assertIn("speaking fluency and pace", text)
        self.assertIn("focus on", text)

        # 2. VC Pitch weighting with identical inputs:
        # Engagement (0.25), Confidence (0.25), Speaking (0.20), Body Language (0.15), Story (0.15)
        # Expected: 60*0.25 + 80*0.25 + 80*0.20 + 60*0.15 + 80*0.15 = 15 + 20 + 16 + 9 + 12 = 72
        score_vc, text_vc = calculate_overall_communication_score(eval_sample, CONTEXT_VC_PITCH)
        self.assertEqual(score_vc, 72)

        # 3. Proportional normalization with missing categories:
        # Suppose Body Language and Engagement are Insufficient Data:
        eval_partial = {
            CAT_SPEAKING_STYLE: {"score": 80},
            CAT_CONFIDENCE: {"score": 70},
            CAT_STORY_QUALITY: {"score": 90},
            CAT_BODY_LANGUAGE: {"score": INSUFFICIENT_DATA},
            CAT_ENGAGEMENT: {"score": INSUFFICIENT_DATA},
        }
        # Active weights in Job Interview: 0.25, 0.25, 0.25 -> total 0.75
        # Weighted sum: 80*0.25 + 70*0.25 + 90*0.25 = 20 + 17.5 + 22.5 = 60.0
        # Normalized: 60.0 / 0.75 = 80
        score_part, _ = calculate_overall_communication_score(eval_partial, CONTEXT_JOB_INTERVIEW)
        self.assertEqual(score_part, 80)

        # 4. Completely empty or insufficient data:
        score_none, text_none = calculate_overall_communication_score({})
        self.assertEqual(score_none, INSUFFICIENT_DATA)
        self.assertIn("Insufficient multimodal data", text_none)


if __name__ == "__main__":
    unittest.main()


