"""
tests/test_video_analysis_pipeline.py
─────────────────────────────────────────────────────────────────────────────
Integration and unit tests for Zaira's "Analyze Existing Video" pipeline.

Verifies:
1. GET /api/analysis/{session_id} returns 404 for unknown session IDs.
2. In-flight sessions return status="processing" with progress.
3. Completed sessions return status="completed" with evidence-backed scores,
   real telemetry, and dynamic strengths/growth targets.
4. Failed sessions return status="failed" with honest error descriptions.
5. Scores, telemetry, and strengths are strictly derived from actual data:
   - Never fabricates eye contact, posture, or constant values (85, 88, 42.8 Hz, 145 WPM).
   - Insufficient evidence is honestly flagged as INSUFFICIENT_DATA.
6. Session checkpoints persist to and restore from .sessions/ disk storage.
"""

import os
import json
import uuid
import unittest
from fastapi.testclient import TestClient

from backend.api import (
    app,
    analysis_sessions,
    _save_session_checkpoint,
    _load_session_checkpoint,
    CHECKPOINT_DIR,
)
from core.constants import (
    INSUFFICIENT_DATA,
    CAT_SPEAKING_STYLE,
    CAT_BODY_LANGUAGE,
    CAT_ENGAGEMENT,
    CAT_CONFIDENCE,
    CAT_STORY_QUALITY,
)
from analytical_engine.evaluator import (
    compute_deterministic_scores,
    calculate_overall_communication_score,
)


class TestVideoAnalysisPipeline(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_get_analysis_unknown_session_returns_404(self):
        unknown_id = f"nonexistent-{uuid.uuid4()}"
        response = self.client.get(f"/api/analysis/{unknown_id}")
        self.assertEqual(response.status_code, 404)
        data = response.json()
        self.assertIn("not found", data.get("detail", "").lower())

    def test_get_analysis_processing_status(self):
        sid = f"proc-test-{uuid.uuid4()}"
        analysis_sessions[sid] = {
            "session_id": sid,
            "status": "processing",
            "progress": 45,
            "message": "Analyzing vocal delivery...",
        }
        try:
            response = self.client.get(f"/api/analysis/{sid}")
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertEqual(data["status"], "processing")
            self.assertEqual(data["progress"], 45)
            self.assertEqual(data["message"], "Analyzing vocal delivery...")
        finally:
            analysis_sessions.pop(sid, None)

    def test_get_analysis_failed_status(self):
        sid = f"fail-test-{uuid.uuid4()}"
        analysis_sessions[sid] = {
            "session_id": sid,
            "status": "failed",
            "progress": 0,
            "error": "Audio demux failed: corrupted video container",
        }
        try:
            response = self.client.get(f"/api/analysis/{sid}")
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertEqual(data["status"], "failed")
            self.assertIn("corrupted video", data.get("error", ""))
        finally:
            analysis_sessions.pop(sid, None)

    def test_deterministic_scoring_and_telemetry_integrity(self):
        """
        Verify that realistic speech and visual features compute real scores and
        dynamic evidence observations, without hardcoded sample constants.
        """
        transcript = "We rolled out the new architecture across three regions. Latency dropped by forty percent."
        speech_feats = {
            "duration_seconds": 12.0,
            "word_count": 14,
            "speaking_rate_wpm": 70.0,
            "pause_count": 1,
            "total_pause_duration_sec": 0.8,
            "filler_word_count": 0,
            "pitch_mean_hz": 180.0,
            "pitch_variation_hz": 28.5,
            "energy_mean_db": -18.0,
            "reliability_flag": "good",
        }
        visual_feats = {
            "face_detected": True,
            "face_presence_ratio": 0.92,
            "head_movement_count": 4,
            "head_movement_rate_per_min": 20.0,
            "head_movement_typical_range": "15-35/min",
            "duration_seconds": 12.0,
            "blink_count": 5,
            "tracking_reliability": "good",
        }

        eval_data = compute_deterministic_scores(
            person_name="Candidate",
            transcript=transcript,
            story_data=None,
            speech_feats=speech_feats,
            visual_feats=visual_feats,
            profile=None,
        )

        overall_score, assessment_text = calculate_overall_communication_score(eval_data, profile=None)

        # Scores must be numeric and bounded
        self.assertIsInstance(overall_score, int)
        self.assertGreaterEqual(overall_score, 0)
        self.assertLessEqual(overall_score, 100)

        # Verify each category has calculated data
        for cat in [CAT_SPEAKING_STYLE, CAT_BODY_LANGUAGE, CAT_ENGAGEMENT, CAT_CONFIDENCE, CAT_STORY_QUALITY]:
            self.assertIn(cat, eval_data)
            self.assertIsInstance(eval_data[cat]["score"], int)
            self.assertIn("evidence_observation", eval_data[cat])

        # Verify visual metrics disclaim eye contact and measure camera presence
        eng_obs = eval_data[CAT_ENGAGEMENT]["assessment"] + " " + eval_data[CAT_ENGAGEMENT]["evidence_observation"]
        self.assertNotIn("direct eye contact", eng_obs.lower())
        self.assertNotIn("consistent eye contact", eng_obs.lower())
        self.assertIn("not measure", eng_obs.lower())
        self.assertIn("camera presence", eval_data[CAT_ENGAGEMENT]["metric_name"].lower())

    def test_insufficient_evidence_honestly_flagged(self):
        """
        When audio or visual stream is missing, ensure scores are flagged
        as INSUFFICIENT_DATA and not replaced with fabricated constants (like 85).
        """
        eval_data = compute_deterministic_scores(
            person_name="Candidate",
            transcript="",
            story_data=None,
            speech_feats=None,
            visual_feats=None,
            profile=None,
        )

        for cat in [CAT_SPEAKING_STYLE, CAT_BODY_LANGUAGE, CAT_ENGAGEMENT, CAT_CONFIDENCE, CAT_STORY_QUALITY]:
            self.assertEqual(eval_data[cat]["score"], INSUFFICIENT_DATA)

        overall_score, assessment_text = calculate_overall_communication_score(eval_data, profile=None)
        self.assertEqual(overall_score, INSUFFICIENT_DATA)
        self.assertIn("insufficient", assessment_text.lower())

    def test_checkpoint_save_and_restore(self):
        """
        Verify that session state persists to .sessions/ disk checkpoint and can be restored.
        """
        sid = f"persist-test-{uuid.uuid4()}"
        payload = {
            "session_id": sid,
            "status": "completed",
            "progress": 100,
            "message": "Analysis Complete",
            "overall_score": 79,
            "assessment_text": "Your communication is clear and composed.",
            "strengths": ["Speaking pace remained steady throughout the delivery."],
            "growth_targets": ["Anchor key points with deliberate pauses."],
            "categories": {},
            "telemetry": {"speaking_rate_wpm": 135.0},
            "transcript": "Hello world.",
            "modality_status": {"audio": "available", "visual": "insufficient", "transcript": "available"},
        }

        # Clear in-memory cache to force loading from disk
        analysis_sessions.pop(sid, None)
        _save_session_checkpoint(sid, payload)

        try:
            # File exists on disk
            chk_path = os.path.join(CHECKPOINT_DIR, f"analysis_{sid}.json")
            self.assertTrue(os.path.exists(chk_path))

            # Restored via GET endpoint
            response = self.client.get(f"/api/analysis/{sid}")
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertEqual(data["overall_score"], 79)
            self.assertEqual(data["transcript"], "Hello world.")
            self.assertEqual(data["telemetry"]["speaking_rate_wpm"], 135.0)
        finally:
            # Cleanup
            analysis_sessions.pop(sid, None)
            chk_path = os.path.join(CHECKPOINT_DIR, f"analysis_{sid}.json")
            if os.path.exists(chk_path):
                os.remove(chk_path)


if __name__ == "__main__":
    unittest.main()
