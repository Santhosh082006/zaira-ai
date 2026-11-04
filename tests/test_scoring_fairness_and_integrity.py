"""
tests/test_scoring_fairness_and_integrity.py
─────────────────────────────────────────────────────────────────────────────
TruthLens AI — Comprehensive Scoring Integrity & Assessment Fairness Test Suite

Validates:
1. Face visibility vs. eye contact / psychological engagement.
2. Entity density vs. factual accuracy / truthfulness.
3. High head movement without automatic punishment (expressive delivery).
4. Missing visual data -> clean "Insufficient Data", never poor score.
5. Missing or corrupted audio -> clean "Insufficient Data".
6. Very short recordings / answers -> guarded against unstable variance.
7. Speaking rate edge cases & gradual, non-punitive heuristic curve.
8. Agreement between backend scores and displayed UI labels.
9. Consistency between individual analysis and comparison modes.
"""

from __future__ import annotations
import json
import unittest

from core.constants import (
    INSUFFICIENT_DATA,
    CAT_SPEAKING_STYLE,
    CAT_BODY_LANGUAGE,
    CAT_ENGAGEMENT,
    CAT_CONFIDENCE,
    CAT_STORY_QUALITY,
    ALL_CATEGORIES,
)
from processors.context_engine.weighting import (
    get_context_profile,
    CONTEXT_JOB_INTERVIEW,
    CONTEXT_VC_PITCH,
    CONTEXT_CASUAL_MEETING,
)
from analytical_engine.vocal_metrics import evaluate_vocal_performance
from analytical_engine.visual_metrics import evaluate_visual_performance
from analytical_engine.evaluator import (
    compute_deterministic_scores,
    calculate_overall_communication_score,
    CATEGORY_STRENGTH_LABELS,
    CATEGORY_IMPROVEMENT_LABELS,
)
from analytical_engine.cross_comparator import compare_multimodal_performance


class TestScoringFairnessAndIntegrity(unittest.TestCase):

    def setUp(self):
        self.profile_job = get_context_profile(CONTEXT_JOB_INTERVIEW)
        self.profile_vc = get_context_profile(CONTEXT_VC_PITCH)
        self.profile_casual = get_context_profile(CONTEXT_CASUAL_MEETING)

    # ── 1. FACE VISIBILITY VS ENGAGEMENT / EYE CONTACT ───────────────────────
    def test_face_visibility_not_called_eye_contact_or_engagement(self):
        """Face presence ratio must be labeled Camera Presence and never claim eye contact."""
        visual = {
            "face_detected": True,
            "face_presence_ratio": 0.94,
            "head_movement_count": 8,
            "head_movement_rate_per_min": 22.0,
            "blink_count": 6,
            "duration_seconds": 20.0,
            "tracking_reliability": "good"
        }
        bl, eng = evaluate_visual_performance(visual, self.profile_job)
        self.assertIsNotNone(eng)
        self.assertEqual(eng.get("metric_name"), "Camera Presence")

        assessment = eng.get("assessment", "").lower()
        evidence = eng.get("evidence_observation", "").lower()

        # Must explicitly state it does NOT measure eye contact or internal engagement
        self.assertIn("does not measure eye gaze, eye contact", assessment)
        self.assertIn("measures camera presence, not eye contact", evidence)
        self.assertIn("percentage of frames with face detected", evidence)

    # ── 2. ENTITY DENSITY VS FACTUAL ACCURACY ────────────────────────────────
    def test_entity_density_not_presented_as_factual_accuracy(self):
        """Entity and event counts reflect narrative detail only, not factual correctness or veracity."""
        # Story 1: Completely fabricated or technically incorrect statements
        story_fictitious = {
            "events": [
                {"description": "The earth is flat and stationary", "time": "ancient times", "location": "everywhere"},
                {"description": "NASA was founded in 1776 by pirates", "time": "1776", "location": "high seas"}
            ],
            "claims": [{"subject": "Earth", "value": "flat"}],
            "all_locations_mentioned": ["high seas", "everywhere"]
        }
        transcript_fictitious = "The earth is flat and stationary everywhere, and NASA was founded in 1776 by pirates."

        res = compute_deterministic_scores(
            "Candidate", transcript_fictitious, story_fictitious, None, None, self.profile_job
        )
        sq = res[CAT_STORY_QUALITY]

        self.assertEqual(sq.get("metric_name"), "Narrative Detail")
        self.assertIn("measures narrative detail and extracted entity density", sq["assessment"])
        self.assertIn("does not measure factual accuracy", sq["assessment"])
        self.assertIn("does not verify factual correctness", sq["evidence_observation"])

        # Must not claim truthfulness, credibility, or factual validity
        sq_str = json.dumps(sq).lower()
        self.assertNotIn("factual accuracy confirmed", sq_str)
        self.assertNotIn("truthful", sq_str)
        self.assertNotIn("credibility", sq_str)

    # ── 3. HIGH HEAD MOVEMENT WITHOUT AUTOMATIC PUNISHMENT ───────────────────
    def test_high_head_movement_not_automatically_punished(self):
        """An animated speaker with 60 movements/min in-frame must not have score collapse to 35."""
        visual_expressive = {
            "face_detected": True,
            "face_presence_ratio": 0.98,
            "head_movement_count": 30,
            "head_movement_rate_per_min": 60.0,  # 60/min (expressive nodder)
            "blink_count": 8,
            "duration_seconds": 30.0,
            "tracking_reliability": "good"
        }
        bl, eng = evaluate_visual_performance(visual_expressive, self.profile_job)
        self.assertIsNotNone(bl)

        # Score must remain in a solid range (>= 80), not crashed to 35 or 45
        self.assertGreaterEqual(bl["score"], 80, f"Expected expressive delivery >= 80, got {bl['score']}")
        # Assessment must recognize expressive delivery rather than calling it nervous
        assessment = bl["assessment"].lower()
        self.assertIn("expressive", assessment)
        self.assertIn("natural", assessment)
        self.assertNotIn("nervous", assessment)
        self.assertNotIn("poor", assessment)

    # ── 4. MISSING FACE DATA PRESERVES INSUFFICIENT DATA ─────────────────────
    def test_missing_face_data_preserves_insufficient_data(self):
        """Missing face tracking must yield INSUFFICIENT_DATA, never an unfavorable score."""
        visual_missing = {
            "face_detected": False,
            "face_presence_ratio": 0.0,
            "head_movement_count": None,
            "tracking_reliability": "no_face_found"
        }
        bl, eng = evaluate_visual_performance(visual_missing, self.profile_job)
        self.assertIsNone(bl)
        self.assertIsNone(eng)

        res = compute_deterministic_scores("Audio Only", "Hello there world.", None, None, visual_missing, self.profile_job)
        self.assertEqual(res[CAT_BODY_LANGUAGE]["score"], INSUFFICIENT_DATA)
        self.assertEqual(res[CAT_ENGAGEMENT]["score"], INSUFFICIENT_DATA)
        self.assertEqual(res[CAT_BODY_LANGUAGE]["what_went_well"], "N/A")
        self.assertEqual(res[CAT_ENGAGEMENT]["what_went_well"], "N/A")

    # ── 5. MISSING OR CORRUPTED AUDIO PRESERVES INSUFFICIENT DATA ────────────
    def test_missing_or_corrupted_audio_preserves_insufficient_data(self):
        """Silent or missing audio must yield INSUFFICIENT_DATA, not a 0 or 35 score."""
        speech_silent = {
            "duration_seconds": 15.0,
            "word_count": 0,
            "speaking_rate_wpm": 0.0,
            "reliability_flag": "all_silence"
        }
        vocal = evaluate_vocal_performance(speech_silent, self.profile_job)
        self.assertIsNone(vocal)

        res = compute_deterministic_scores("Silent Video", "", None, speech_silent, None, self.profile_job)
        self.assertEqual(res[CAT_SPEAKING_STYLE]["score"], INSUFFICIENT_DATA)
        self.assertEqual(res[CAT_SPEAKING_STYLE]["what_went_well"], "N/A")

    # ── 6. VERY SHORT RECORDINGS GUARDED ─────────────────────────────────────
    def test_very_short_recordings_guarded(self):
        """Snippets < 3s or < 4 words cannot support stable speaking pace evaluation."""
        short_speech = {
            "duration_seconds": 2.0,
            "word_count": 3,
            "speaking_rate_wpm": 90.0,
            "reliability_flag": "good"
        }
        vocal = evaluate_vocal_performance(short_speech, self.profile_job)
        self.assertIsNone(vocal, "Short audio snippets under 3s must return None due to variance.")

    # ── 7. SPEAKING RATE EDGE CASES & GRADUAL HEURISTIC CURVE ────────────────
    def test_speaking_rate_edge_cases_and_non_punitive_gradual_curve(self):
        """Thoughtful deliberate pacing (e.g. 95 WPM) receives a fair, non-punitive score."""
        deliberate_speech = {
            "duration_seconds": 25.0,
            "word_count": 40,
            "speaking_rate_wpm": 96.0,  # Below 115 WPM target, but composed
            "pause_count": 3,
            "total_pause_duration_sec": 3.0,
            "filler_word_count": 0,
            "reliability_flag": "good"
        }
        vocal = evaluate_vocal_performance(deliberate_speech, self.profile_job)
        self.assertIsNotNone(vocal)
        self.assertGreaterEqual(vocal["score"], 78, f"Expected deliberate speech >= 78, got {vocal['score']}")
        self.assertEqual(vocal["speaking_rate_wpm"], 96.0)
        self.assertIn("heuristic guideline", vocal["evidence_observation"])

    # ── 8. AGREEMENT BETWEEN BACKEND SCORES AND DISPLAYED LABELS ─────────────
    def test_agreement_between_backend_scores_and_displayed_labels(self):
        """Verify label consistency between backend evaluation and frontend presentation."""
        self.assertEqual(CATEGORY_STRENGTH_LABELS[CAT_STORY_QUALITY], "narrative detail and event richness")
        self.assertEqual(CATEGORY_STRENGTH_LABELS[CAT_ENGAGEMENT], "consistent camera presence")
        self.assertEqual(CATEGORY_STRENGTH_LABELS[CAT_CONFIDENCE], "composed presentation delivery")

        # Test overall communication score normalization with partial categories
        partial_eval = {
            CAT_SPEAKING_STYLE: {"score": 90},
            CAT_BODY_LANGUAGE: {"score": INSUFFICIENT_DATA},
            CAT_ENGAGEMENT: {"score": INSUFFICIENT_DATA},
            CAT_CONFIDENCE: {"score": 90},
            CAT_STORY_QUALITY: {"score": 85},
        }
        score, assessment = calculate_overall_communication_score(partial_eval, self.profile_job)
        self.assertIsInstance(score, int)
        self.assertGreaterEqual(score, 80)
        self.assertIn("communication", assessment.lower())

    # ── 9. CONSISTENCY BETWEEN INDIVIDUAL AND COMPARISON MODES ───────────────
    def test_consistency_between_individual_and_comparison_modes(self):
        """Compare mode must use identical category definitions and non-punitive observations."""
        eval_a = {
            CAT_SPEAKING_STYLE: {"score": 85},
            CAT_STORY_QUALITY: {"score": 80},
            CAT_ENGAGEMENT: {"score": 90},
            CAT_BODY_LANGUAGE: {"score": 88},
            CAT_CONFIDENCE: {"score": 86},
        }
        eval_b = {
            CAT_SPEAKING_STYLE: {"score": 92},
            CAT_STORY_QUALITY: {"score": 85},
            CAT_ENGAGEMENT: {"score": 94},
            CAT_BODY_LANGUAGE: {"score": 90},
            CAT_CONFIDENCE: {"score": 90},
        }
        visual_a = {"head_movement_rate_per_min": 25.0, "face_presence_ratio": 0.95}
        visual_b = {"head_movement_rate_per_min": 45.0, "face_presence_ratio": 0.98}

        comp = compare_multimodal_performance(eval_a, eval_b, visual_a=visual_a, visual_b=visual_b, profile_key=CONTEXT_JOB_INTERVIEW)

        cat_names = [c["category"] for c in comp["category_comparisons"]]
        self.assertIn("Narrative Detail", cat_names)
        self.assertIn("Camera Presence", cat_names)
        self.assertIn("Speaking Style", cat_names)
        self.assertIn("Body Language", cat_names)

        # Check metric delta description
        deltas = {d["metric"]: d for d in comp["metric_deltas"]}
        self.assertIn("Camera Presence", deltas)
        self.assertIn("viewport", deltas["Camera Presence"]["interpretation"])


if __name__ == "__main__":
    unittest.main()
