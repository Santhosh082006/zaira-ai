"""
tests/test_three_features_and_scoring.py
─────────────────────────────────────────────────────────────────────────────
Comprehensive Verification Suite for TruthLens AI Three-Feature Architecture:

TEST 1:  Live Camera flow: record/video -> analyze -> actual results appear.
TEST 2:  Upload weak/poor measured video -> results reflect actual measured data.
TEST 3:  Upload strong/good measured video -> results genuinely differ.
TEST 4:  Same video through Live and Upload -> downstream metrics are consistent.
TEST 5:  Compare Video A + Video B -> both independent analyses appear.
TEST 6:  Comparison metrics are derived from actual A/B measurements.
TEST 7:  Change Video A -> old A results disappear.
TEST 8:  Change Video B -> old B results disappear.
TEST 9:  Missing visual data -> no fabricated body-language score ("Insufficient Data").
TEST 10: Missing speech data -> no fabricated speaking score ("Insufficient Data").
TEST 11: Good performance still receives improvement suggestions.
TEST 12: Poor performance receives concrete improvement suggestions.
TEST 13: PDF values match UI values.
TEST 14: No truthfulness/deception/lying scores are produced.
"""

from __future__ import annotations
import os
import sys
import json
import unittest
import zlib
import re
import streamlit as st

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from core.constants import (
    INSUFFICIENT_DATA,
    FORBIDDEN_DECEPTION_TERMS,
    CAT_SPEAKING_STYLE,
    CAT_BODY_LANGUAGE,
    CAT_ENGAGEMENT,
    CAT_CONFIDENCE,
    CAT_STORY_QUALITY,
    ALL_CATEGORIES
)
from processors.context_engine.weighting import get_context_profile, CONTEXT_JOB_INTERVIEW, CONTEXT_VC_PITCH, CONTEXT_CASUAL_MEETING
from analytical_engine.vocal_metrics import evaluate_vocal_performance
from analytical_engine.visual_metrics import evaluate_visual_performance
from analytical_engine.evaluator import compute_deterministic_scores, evaluate_account_with_explanation
from analytical_engine.cross_comparator import compare_multimodal_performance
from services.report_generator import generate_performance_report, generate_evidence_report
from app import calculate_analysis_coverage, reset_person_downstream


def _extract_pdf_text(pdf_bytes: bytes) -> str:
    streams = re.findall(rb'stream[\r\n]+(.*?)[\r\n]+endstream', pdf_bytes, re.DOTALL)
    all_text = []
    for s in streams:
        try:
            decomp = zlib.decompress(s).decode('latin-1', 'replace')
            all_text.append(decomp)
        except Exception:
            all_text.append(s.decode('latin-1', 'replace'))
    return "\n".join(all_text)


class TestThreeFeaturesAndScoring(unittest.TestCase):

    def setUp(self):
        self.profile_job = get_context_profile(CONTEXT_JOB_INTERVIEW)
        self.profile_vc = get_context_profile(CONTEXT_VC_PITCH)
        self.profile_casual = get_context_profile(CONTEXT_CASUAL_MEETING)

    # ── TEST 1: Live Camera flow -> analyze -> actual results appear ─────────
    def test_01_live_camera_analysis_produces_actual_results(self):
        speech = {
            "duration_seconds": 15.0,
            "word_count": 35,
            "speaking_rate_wpm": 140.0,
            "pause_count": 2,
            "total_pause_duration_sec": 1.8,
            "filler_word_count": 0,
            "reliability_flag": "good"
        }
        visual = {
            "face_detected": True,
            "face_presence_ratio": 0.96,
            "head_movement_count": 6,
            "head_movement_rate_per_min": 24.0,
            "blink_count": 5,
            "duration_seconds": 15.0,
            "tracking_reliability": "good"
        }
        transcript = "I arrived at the company headquarters for the interview at precisely nine o'clock."
        story = {"events": [{"time": "9:00 AM", "location": "Headquarters", "description": "Arrived for interview"}]}

        eval_res = compute_deterministic_scores("Live Performer", transcript, story, speech, visual, self.profile_job)

        self.assertIsInstance(eval_res, dict)
        for cat in ALL_CATEGORIES:
            self.assertIn(cat, eval_res)
            self.assertIsInstance(eval_res[cat]["score"], int)
            self.assertGreater(eval_res[cat]["score"], 0)
            self.assertNotEqual(eval_res[cat]["what_went_well"], "N/A")

    # ── TEST 2: Weak measured video -> results reflect actual measured data ──
    def test_02_weak_video_receives_lower_evidence_backed_scores(self):
        # Weak speech: 60 WPM (very slow), 6 fillers, 45% pause time
        weak_speech = {
            "duration_seconds": 20.0,
            "word_count": 20,
            "speaking_rate_wpm": 60.0,
            "pause_count": 8,
            "total_pause_duration_sec": 9.0,
            "filler_word_count": 6,
            "reliability_flag": "good"
        }
        # Weak visual: 48% face presence, 85/min head movement rate (excessive movement)
        weak_visual = {
            "face_detected": True,
            "face_presence_ratio": 0.48,
            "head_movement_count": 28,
            "head_movement_rate_per_min": 84.0,
            "blink_count": 18,
            "duration_seconds": 20.0,
            "tracking_reliability": "good"
        }
        transcript = "Uh well I guess maybe I did something."

        res = compute_deterministic_scores("Weak Candidate", transcript, None, weak_speech, weak_visual, self.profile_job)

        spk_score = res[CAT_SPEAKING_STYLE]["score"]
        bl_score = res[CAT_BODY_LANGUAGE]["score"]
        eng_score = res[CAT_ENGAGEMENT]["score"]

        # Weak measurements must mathematically produce significantly lower scores (< 65)
        self.assertLess(spk_score, 65, f"Weak speech expected <65, got {spk_score}")
        self.assertLess(bl_score, 65, f"Excessive head movement expected <65, got {bl_score}")
        self.assertLess(eng_score, 60, f"Low camera presence expected <60, got {eng_score}")

        # Recommendations must specifically reference measured defects
        self.assertIn("filler", res[CAT_SPEAKING_STYLE]["what_needs_improvement"].lower())
        self.assertIn("head", res[CAT_BODY_LANGUAGE]["what_needs_improvement"].lower())

    # ── TEST 3: Strong measured video -> results genuinely differ ────────────
    def test_03_strong_video_differentiates_from_weak_video(self):
        strong_speech = {
            "duration_seconds": 30.0,
            "word_count": 70,
            "speaking_rate_wpm": 140.0,
            "pause_count": 3,
            "total_pause_duration_sec": 2.5,
            "filler_word_count": 0,
            "reliability_flag": "good"
        }
        strong_visual = {
            "face_detected": True,
            "face_presence_ratio": 0.98,
            "head_movement_count": 12,
            "head_movement_rate_per_min": 24.0,
            "blink_count": 8,
            "duration_seconds": 30.0,
            "tracking_reliability": "good"
        }
        transcript = "First I launched the project in March, then we achieved all quarterly milestones with great results."
        story = {"events": [{"time": "March", "location": "Office", "description": "Launched project"}]}

        res_strong = compute_deterministic_scores("Strong Candidate", transcript, story, strong_speech, strong_visual, self.profile_job)

        spk_score = res_strong[CAT_SPEAKING_STYLE]["score"]
        bl_score = res_strong[CAT_BODY_LANGUAGE]["score"]
        eng_score = res_strong[CAT_ENGAGEMENT]["score"]

        self.assertGreaterEqual(spk_score, 85, f"Strong speech expected >=85, got {spk_score}")
        self.assertGreaterEqual(bl_score, 85, f"Composed posture expected >=85, got {bl_score}")
        self.assertGreaterEqual(eng_score, 85, f"Steady presence expected >=85, got {eng_score}")

    # ── TEST 4: Same video through Live and Upload produces identical result ─
    def test_04_same_video_through_live_and_upload_produces_consistent_result(self):
        shared_speech = {
            "duration_seconds": 25.0,
            "word_count": 55,
            "speaking_rate_wpm": 132.0,
            "pause_count": 3,
            "total_pause_duration_sec": 2.2,
            "filler_word_count": 1,
            "reliability_flag": "good"
        }
        shared_visual = {
            "face_detected": True,
            "face_presence_ratio": 0.94,
            "head_movement_count": 10,
            "head_movement_rate_per_min": 24.0,
            "blink_count": 7,
            "duration_seconds": 25.0,
            "tracking_reliability": "good"
        }
        transcript = "I presented our quarterly roadmap to the executive board yesterday afternoon."
        story = {"events": [{"time": "yesterday afternoon", "location": "boardroom", "description": "presented roadmap"}]}

        res_live = compute_deterministic_scores("Live Performer", transcript, story, shared_speech, shared_visual, self.profile_job)
        res_upload = compute_deterministic_scores("Uploaded Video", transcript, story, shared_speech, shared_visual, self.profile_job)

        for cat in ALL_CATEGORIES:
            self.assertEqual(
                res_live[cat]["score"],
                res_upload[cat]["score"],
                f"Category {cat} should be identical across Live and Upload for identical inputs."
            )

    # ── TEST 5: Compare Video A + Video B -> both analyses appear ────────────
    def test_05_compare_videos_renders_independent_analyses(self):
        eval_a = {
            CAT_SPEAKING_STYLE: {"score": 62, "assessment": "Slow pace"},
            CAT_BODY_LANGUAGE: {"score": 58, "assessment": "High movement"},
            CAT_ENGAGEMENT: {"score": 65, "assessment": "Moderate presence"},
            CAT_CONFIDENCE: {"score": 61, "assessment": "Deliberate"},
            CAT_STORY_QUALITY: {"score": 60, "assessment": "Basic"}
        }
        eval_b = {
            CAT_SPEAKING_STYLE: {"score": 90, "assessment": "Fluent pace"},
            CAT_BODY_LANGUAGE: {"score": 92, "assessment": "Composed posture"},
            CAT_ENGAGEMENT: {"score": 94, "assessment": "Continuous gaze"},
            CAT_CONFIDENCE: {"score": 92, "assessment": "High composure"},
            CAT_STORY_QUALITY: {"score": 85, "assessment": "Detailed sequence"}
        }

        res = compare_multimodal_performance(eval_a, eval_b, profile_key=CONTEXT_JOB_INTERVIEW)

        self.assertIn("winner", res)
        self.assertIn("outcome_badge", res)
        self.assertIn("metric_deltas", res)
        self.assertIn("category_comparisons", res)
        self.assertEqual(len(res["category_comparisons"]), 5)

    # ── TEST 6: Comparison metrics derived from actual A/B measurements ───────
    def test_06_comparison_metrics_derived_from_actual_measurements(self):
        speech_a = {"speaking_rate_wpm": 82.0, "pause_count": 6, "filler_word_count": 4}
        speech_b = {"speaking_rate_wpm": 143.0, "pause_count": 2, "filler_word_count": 0}
        visual_a = {"head_movement_rate_per_min": 97.0, "face_presence_ratio": 0.61}
        visual_b = {"head_movement_rate_per_min": 24.0, "face_presence_ratio": 0.96}

        eval_a = compute_deterministic_scores("A", "text A", None, {**speech_a, "duration_seconds": 20.0, "reliability_flag": "good"}, {**visual_a, "face_detected": True, "tracking_reliability": "good"}, self.profile_job)
        eval_b = compute_deterministic_scores("B", "text B", None, {**speech_b, "duration_seconds": 20.0, "reliability_flag": "good"}, {**visual_b, "face_detected": True, "tracking_reliability": "good"}, self.profile_job)

        comp = compare_multimodal_performance(eval_a, eval_b, speech_a, speech_b, visual_a, visual_b, profile_key=CONTEXT_JOB_INTERVIEW)

        deltas = {d["metric"]: d for d in comp["metric_deltas"]}
        self.assertIn("Speaking Pace", deltas)
        self.assertEqual(deltas["Speaking Pace"]["val_a"], "82 WPM")
        self.assertEqual(deltas["Speaking Pace"]["val_b"], "143 WPM")
        self.assertEqual(deltas["Speaking Pace"]["delta"], "+61 WPM")

        self.assertIn("Head Movement Rate", deltas)
        self.assertEqual(deltas["Head Movement Rate"]["val_a"], "97.0/min")
        self.assertEqual(deltas["Head Movement Rate"]["val_b"], "24.0/min")
        self.assertEqual(deltas["Head Movement Rate"]["delta"], "-73.0/min")

        self.assertIn("Camera Presence", deltas)
        self.assertEqual(deltas["Camera Presence"]["val_a"], "61%")
        self.assertEqual(deltas["Camera Presence"]["val_b"], "96%")

        # Winner must be Video B based on measured criteria
        self.assertEqual(comp["winner"], "Video B")
        self.assertIn("🏆 Stronger Measured Performance: Video B", comp["outcome_badge"])

    # ── TEST 7: Change Video A -> old A results disappear ────────────────────
    def test_07_change_video_a_invalidates_only_a(self):
        st.session_state["transcript_a"] = "Old transcript A"
        st.session_state["speech_features_a"] = {"speaking_rate_wpm": 120}
        st.session_state["evaluation_data_a"] = {"speaking_style": {"score": 80}}

        st.session_state["transcript_b"] = "Preserved transcript B"
        st.session_state["speech_features_b"] = {"speaking_rate_wpm": 145}
        st.session_state["evaluation_data_b"] = {"speaking_style": {"score": 90}}
        st.session_state["comparison_result"] = {"status": "compared"}

        # Simulate Video A changing
        reset_person_downstream("a")

        # A's results must be cleared
        self.assertEqual(st.session_state.get("transcript_a"), "")
        self.assertIsNone(st.session_state.get("speech_features_a"))
        self.assertIsNone(st.session_state.get("evaluation_data_a"))
        self.assertIsNone(st.session_state.get("comparison_result"))

        # B's results MUST be preserved!
        self.assertEqual(st.session_state.get("transcript_b"), "Preserved transcript B")
        self.assertEqual(st.session_state.get("speech_features_b", {}).get("speaking_rate_wpm"), 145)
        self.assertEqual(st.session_state.get("evaluation_data_b", {}).get("speaking_style", {}).get("score"), 90)

    # ── TEST 8: Change Video B -> old B results disappear ────────────────────
    def test_08_change_video_b_invalidates_only_b(self):
        st.session_state["transcript_a"] = "Preserved transcript A"
        st.session_state["speech_features_a"] = {"speaking_rate_wpm": 130}
        st.session_state["evaluation_data_a"] = {"speaking_style": {"score": 85}}

        st.session_state["transcript_b"] = "Old transcript B"
        st.session_state["speech_features_b"] = {"speaking_rate_wpm": 90}
        st.session_state["evaluation_data_b"] = {"speaking_style": {"score": 60}}
        st.session_state["comparison_result"] = {"status": "compared"}

        # Simulate Video B changing
        reset_person_downstream("b")

        # B's results must be cleared
        self.assertEqual(st.session_state.get("transcript_b"), "")
        self.assertIsNone(st.session_state.get("speech_features_b"))
        self.assertIsNone(st.session_state.get("evaluation_data_b"))
        self.assertIsNone(st.session_state.get("comparison_result"))

        # A's results MUST be preserved!
        self.assertEqual(st.session_state.get("transcript_a"), "Preserved transcript A")
        self.assertEqual(st.session_state.get("speech_features_a", {}).get("speaking_rate_wpm"), 130)
        self.assertEqual(st.session_state.get("evaluation_data_a", {}).get("speaking_style", {}).get("score"), 85)

    # ── TEST 9: Missing visual data -> no fabricated body language score ─────
    def test_09_missing_visual_data_no_fabricated_scores(self):
        speech = {
            "duration_seconds": 20.0,
            "word_count": 45,
            "speaking_rate_wpm": 135.0,
            "pause_count": 2,
            "total_pause_duration_sec": 1.5,
            "filler_word_count": 0,
            "reliability_flag": "good"
        }
        res = compute_deterministic_scores("Audio Only", "Valid spoken narrative text here.", None, speech, None, self.profile_job)

        self.assertEqual(res[CAT_BODY_LANGUAGE]["score"], INSUFFICIENT_DATA)
        self.assertEqual(res[CAT_BODY_LANGUAGE]["what_went_well"], "N/A")
        self.assertEqual(res[CAT_BODY_LANGUAGE]["what_needs_improvement"], "N/A")

        self.assertEqual(res[CAT_ENGAGEMENT]["score"], INSUFFICIENT_DATA)
        self.assertEqual(res[CAT_ENGAGEMENT]["what_went_well"], "N/A")
        self.assertEqual(res[CAT_ENGAGEMENT]["what_needs_improvement"], "N/A")

    # ── TEST 10: Missing speech data -> no fabricated speaking score ─────────
    def test_10_missing_speech_data_no_fabricated_scores(self):
        visual = {
            "face_detected": True,
            "face_presence_ratio": 0.95,
            "head_movement_count": 8,
            "head_movement_rate_per_min": 24.0,
            "blink_count": 6,
            "duration_seconds": 20.0,
            "tracking_reliability": "good"
        }
        res = compute_deterministic_scores("Silent Video", "", None, None, visual, self.profile_job)

        self.assertEqual(res[CAT_SPEAKING_STYLE]["score"], INSUFFICIENT_DATA)
        self.assertEqual(res[CAT_SPEAKING_STYLE]["what_went_well"], "N/A")
        self.assertEqual(res[CAT_SPEAKING_STYLE]["what_needs_improvement"], "N/A")

    # ── TEST 11: Good performance still receives improvement suggestions ────
    def test_11_good_performance_receives_actionable_suggestions(self):
        speech = {
            "duration_seconds": 30.0,
            "word_count": 70,
            "speaking_rate_wpm": 140.0,
            "pause_count": 2,
            "total_pause_duration_sec": 1.5,
            "filler_word_count": 0,
            "reliability_flag": "good"
        }
        visual = {
            "face_detected": True,
            "face_presence_ratio": 0.98,
            "head_movement_count": 10,
            "head_movement_rate_per_min": 20.0,
            "blink_count": 6,
            "duration_seconds": 30.0,
            "tracking_reliability": "good"
        }
        transcript = "I led the engineering team through the product launch last quarter."
        story = {"events": [{"time": "last quarter", "location": "office", "description": "led launch"}]}

        res = compute_deterministic_scores("Top Performer", transcript, story, speech, visual, self.profile_job)

        # Must not be a naive 100/100
        for cat in ALL_CATEGORIES:
            score = res[cat]["score"]
            self.assertIsInstance(score, int)
            self.assertLessEqual(score, 96, f"Category {cat} should not be 100/100, got {score}")

            # Must have actionable suggestions
            rec = res[cat].get("practical_recommendation", "")
            self.assertTrue(len(rec) > 10, f"Category {cat} missing actionable recommendation.")
            self.assertNotEqual(rec, "N/A")

    # ── TEST 12: Poor performance receives concrete improvement suggestions ──
    def test_12_poor_performance_receives_concrete_suggestions(self):
        weak_speech = {
            "duration_seconds": 25.0,
            "word_count": 25,
            "speaking_rate_wpm": 60.0,
            "pause_count": 8,
            "total_pause_duration_sec": 10.0,
            "filler_word_count": 7,
            "reliability_flag": "good"
        }
        res = evaluate_vocal_performance(weak_speech, self.profile_job)

        self.assertIsNotNone(res)
        self.assertIn("filler", res["what_needs_improvement"].lower())
        self.assertTrue("breath" in res["practical_recommendation"].lower() or "transition" in res["practical_recommendation"].lower())

    # ── TEST 13: PDF values match UI values ──────────────────────────────────
    def test_13_pdf_values_match_ui_values(self):
        speech = {
            "duration_seconds": 20.0,
            "word_count": 45,
            "speaking_rate_wpm": 135.0,
            "pause_count": 2,
            "total_pause_duration_sec": 1.5,
            "filler_word_count": 0,
            "reliability_flag": "good"
        }
        visual = {
            "face_detected": True,
            "face_presence_ratio": 0.95,
            "head_movement_count": 8,
            "head_movement_rate_per_min": 24.0,
            "blink_count": 6,
            "duration_seconds": 20.0,
            "tracking_reliability": "good"
        }
        transcript = "I met with the venture capital partners at their Menlo Park office on Monday morning."
        story = {"events": [{"time": "Monday morning", "location": "Menlo Park", "description": "Met with partners"}]}

        eval_data = compute_deterministic_scores("Candidate", transcript, story, speech, visual, self.profile_job)

        spk_score = eval_data[CAT_SPEAKING_STYLE]["score"]
        bl_score = eval_data[CAT_BODY_LANGUAGE]["score"]

        pdf_bytes = generate_performance_report(
            person_label="Candidate",
            story=story,
            speech=speech,
            visual=visual,
            eval_data=eval_data,
            coverage_score=95,
            coverage_breakdown=["Speech Analysis ✅ Complete", "Visual Analysis ✅ Complete"]
        )

        extracted = _extract_pdf_text(pdf_bytes)

        # PDF must match exact UI scores and measurements
        unescaped = extracted.replace("\\(", "(").replace("\\)", ")")
        self.assertIn(f"Speaking Style & Fluency (Score: {spk_score}/100)", unescaped)
        self.assertIn(f"Body Language & Posture (Score: {bl_score}/100)", unescaped)
        self.assertIn("135 WPM", unescaped)
        self.assertIn("24.0/min", unescaped)

    # ── TEST 14: No truthfulness/deception/lying scores produced ─────────────
    def test_14_no_truth_deception_scores_produced(self):
        speech = {"duration_seconds": 20.0, "word_count": 40, "speaking_rate_wpm": 120.0, "reliability_flag": "good"}
        visual = {"face_detected": True, "face_presence_ratio": 0.90, "head_movement_count": 8, "duration_seconds": 20.0, "tracking_reliability": "good"}
        transcript = "I was at the library study room from 2 PM to 4 PM."
        story = {"events": [{"time": "2 PM", "location": "library", "description": "Studied"}]}

        eval_data = compute_deterministic_scores("Performer", transcript, story, speech, visual, self.profile_job)
        eval_str = json.dumps(eval_data).lower()

        for term in FORBIDDEN_DECEPTION_TERMS:
            self.assertNotIn(term, eval_str, f"Forbidden term '{term}' found in evaluation output.")

        comp = compare_multimodal_performance(eval_data, eval_data, profile_key=CONTEXT_JOB_INTERVIEW)
        comp_str = json.dumps(comp).lower()
        for term in FORBIDDEN_DECEPTION_TERMS:
            self.assertNotIn(term, comp_str, f"Forbidden term '{term}' found in comparison output.")


if __name__ == "__main__":
    unittest.main()
