"""
tests/test_evidence_grounded_assessment.py
─────────────────────────────────────────────────────────────────────────────
Comprehensive Regression Suite for TruthLens Evidence-Grounded Assessment:

Ensures that every assessment statement is strictly traceable to:
1. Actual measured speech metrics
2. Actual measured visual metrics
3. Actual transcript/story structure
4. Explicitly available contextual information

The evaluator MUST NOT produce unsupported claims or hallucinations:
- NO eye contact claims ("maintains eye contact", "stable eye contact")
- NO tone/prosody claims ("tone is steady", "conversational tone")
- NO hesitation claims unless measured
- NO internal psychological state inferences ("speaker is confident", "nervous", "lacks confidence")
- NO credibility or truthfulness evaluations ("enhances the credibility of the claims", "credible", "lying")
- Deception words in speaker transcripts do not influence communication scores
"""

import sys
import os
import unittest
import json

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from core.constants import (
    CAT_CONFIDENCE,
    CAT_BODY_LANGUAGE,
    CAT_SPEAKING_STYLE,
    CAT_ENGAGEMENT,
    CAT_STORY_QUALITY,
    ALL_CATEGORIES,
    INSUFFICIENT_DATA
)
from processors.context_engine.weighting import get_context_profile, CONTEXT_JOB_INTERVIEW
from analytical_engine.evaluator import compute_deterministic_scores, evaluate_account_with_explanation
from services.story_analyzer import _sanitize_assessment_text, _enforce_data_integrity


class TestEvidenceGroundedAssessment(unittest.TestCase):

    def setUp(self):
        self.profile = get_context_profile(CONTEXT_JOB_INTERVIEW)

    # ── TEST 1: Section 12 Required Test Case ────────────────────────────────
    def test_section_12_evaluator_never_produces_unsupported_claims(self):
        """
        Given:
          WPM = 124
          pauses = 0
          few fillers
          head movement = 117.4/min
          face presence = high (0.96)
          NO eye-contact metric
          NO tone metric
          NO hesitation metric

        The output MUST NOT contain:
          'maintains eye contact', 'steady tone', 'hesitation', 'nervous',
          'deceptive', 'credible', 'truthful', 'lying'

        It MAY / SHOULD contain:
          '124 WPM', 'few filler words' or 'filler words', 'no long pauses detected',
          '117.4', 'face visibility was consistent'
        """
        speech = {
            "duration_seconds": 25.0,
            "word_count": 52,
            "speaking_rate_wpm": 124.0,
            "pause_count": 0,
            "total_pause_duration_sec": 0.0,
            "filler_word_count": 0,
            "reliability_flag": "good"
        }
        visual = {
            "face_detected": True,
            "face_presence_ratio": 0.96,
            "head_movement_count": 49,
            "head_movement_rate_per_min": 117.4,
            "blink_count": 6,
            "duration_seconds": 25.0,
            "tracking_reliability": "good"
        }
        transcript = "I arrived at the headquarters at nine o'clock and presented our roadmap to the team."
        story = {"events": [{"time": "9:00 AM", "location": "headquarters", "description": "presented roadmap"}]}

        eval_data = compute_deterministic_scores(
            person_name="Candidate",
            transcript=transcript,
            story_data=story,
            speech_feats=speech,
            visual_feats=visual,
            profile=self.profile
        )

        all_text = json.dumps(eval_data).lower()

        # MUST NOT contain unsupported claims
        unsupported_claims = [
            "maintains eye contact",
            "eye contact",
            "steady tone",
            "conversational tone",
            "hesitation",
            "hesitance",
            "nervous",
            "deceptive",
            "credible",
            "credibility",
            "truthful",
            "lying",
            "lacks confidence",
            "assertive"
        ]
        for term in unsupported_claims:
            self.assertNotIn(
                term,
                all_text,
                f"Evaluation contains forbidden unsupported claim: '{term}'"
            )

        # SHOULD contain grounded observations
        self.assertIn("124 wpm", all_text)
        self.assertIn("no long pauses detected", all_text)
        self.assertIn("117.4", all_text)
        self.assertIn("face visibility", all_text)

    # ── TEST 2: Confidence Indicators observable language only ───────────────
    def test_confidence_indicators_uses_observable_language_only(self):
        speech = {
            "duration_seconds": 15.0,
            "word_count": 31,
            "speaking_rate_wpm": 124.0,
            "pause_count": 0,
            "total_pause_duration_sec": 0.0,
            "filler_word_count": 0,
            "reliability_flag": "good"
        }
        visual = {
            "face_detected": True,
            "face_presence_ratio": 0.95,
            "head_movement_count": 6,
            "head_movement_rate_per_min": 24.0,
            "blink_count": 5,
            "duration_seconds": 15.0,
            "tracking_reliability": "good"
        }

        res = compute_deterministic_scores("Performer", "I managed the rollout.", None, speech, visual, self.profile)
        ci = res[CAT_CONFIDENCE]

        # Must explicitly note internal confidence cannot be determined from signals alone
        self.assertIn("confidence as an internal state cannot be determined", ci["assessment"])
        self.assertNotIn("speaker is confident", ci["assessment"].lower())
        self.assertNotIn("speaker is nervous", ci["assessment"].lower())

    # ── TEST 3: Body Language describes movement, not emotion ────────────────
    def test_body_language_describes_movement_rate_not_emotion(self):
        visual = {
            "face_detected": True,
            "face_presence_ratio": 0.92,
            "head_movement_count": 58,
            "head_movement_rate_per_min": 117.4,
            "blink_count": 7,
            "duration_seconds": 30.0,
            "tracking_reliability": "good"
        }
        res = compute_deterministic_scores("Performer", "Test transcript.", None, None, visual, self.profile)
        bl = res[CAT_BODY_LANGUAGE]

        self.assertIn("117.4 movements/min", bl["assessment"])
        self.assertIn("15-35", bl["assessment"])
        self.assertNotIn("nervous", json.dumps(bl).lower())
        self.assertNotIn("deception", json.dumps(bl).lower())
        self.assertNotIn("uncomfortable", json.dumps(bl).lower())

    # ── TEST 4: Eye Contact is never claimed ─────────────────────────────────
    def test_eye_contact_never_claimed(self):
        visual = {
            "face_detected": True,
            "face_presence_ratio": 0.98,
            "head_movement_count": 10,
            "head_movement_rate_per_min": 20.0,
            "blink_count": 5,
            "duration_seconds": 30.0,
            "tracking_reliability": "good"
        }
        res = compute_deterministic_scores("Performer", "Test transcript.", None, None, visual, self.profile)
        eng = res[CAT_ENGAGEMENT]

        # Must mention face visibility, NEVER eye contact
        self.assertIn("face visibility", eng["assessment"].lower())
        self.assertNotIn("eye contact", json.dumps(eng).lower())

    # ── TEST 5: Story Quality evaluates specificity, not credibility ─────────
    def test_story_quality_evaluates_structure_not_credibility(self):
        story = {
            "events": [
                {"time": "Monday 9 AM", "location": "Room 101", "description": "Met with stakeholders"}
            ],
            "claims": [
                {"subject": "Stakeholders", "attribute": "approved", "value": "budget"}
            ],
            "all_locations_mentioned": ["Room 101"],
            "all_people_mentioned": ["stakeholders"]
        }
        res = compute_deterministic_scores("Performer", "Spoken narrative text here.", story, None, None, self.profile)
        sq = res[CAT_STORY_QUALITY]

        self.assertNotIn("credib", json.dumps(sq).lower())
        self.assertNotIn("truth", json.dumps(sq).lower())
        self.assertNotIn("honest", json.dumps(sq).lower())
        self.assertNotIn("believ", json.dumps(sq).lower())
        self.assertIn("concrete examples that improve specificity", sq["what_went_well"])

    # ── TEST 6: Speaker transcript with deception words does not penalize ────
    def test_transcript_deception_words_do_not_penalize_scores(self):
        """
        When the speaker says 'I am not a liar, I wasn't lying about the numbers',
        the scores must NOT be penalized or treated as deception findings.
        """
        speech = {
            "duration_seconds": 20.0,
            "word_count": 45,
            "speaking_rate_wpm": 135.0,
            "pause_count": 2,
            "total_pause_duration_sec": 1.2,
            "filler_word_count": 0,
            "reliability_flag": "good"
        }
        transcript_clean = "I presented our quarterly roadmap to the board on Monday morning."
        transcript_deception_words = "I am not a liar, I wasn't lying about the quarterly roadmap we presented on Monday morning."

        res_clean = compute_deterministic_scores("Performer", transcript_clean, None, speech, None, self.profile)
        res_deception_words = compute_deterministic_scores("Performer", transcript_deception_words, None, speech, None, self.profile)

        # Speaking style and confidence scores must not be penalized
        self.assertEqual(
            res_clean[CAT_SPEAKING_STYLE]["score"],
            res_deception_words[CAT_SPEAKING_STYLE]["score"]
        )
        self.assertEqual(
            res_clean[CAT_CONFIDENCE]["score"],
            res_deception_words[CAT_CONFIDENCE]["score"]
        )

    # ── TEST 7: Sanitizer scrubs adversarial hallucinations ──────────────────
    def test_sanitizer_scrubs_all_hallucinations(self):
        adversarial_texts = [
            ("The speaker tone is steady and conversational tone.", "speaking pace is steady and conversational speaking pace."),
            ("Moments where hesitance is noticeable during speech.", "measured pauses between statements during speech."),
            ("The speaker maintains eye contact and eye contact was strong.", "the speaker maintains camera face visibility and consistent face visibility."),
            ("This enhances the credibility of the claims made.", "this provides additional detail to the narrative."),
            ("The speaker is confident and demonstrates moderate confidence.", "The speaker maintains a steady speaking pace and The speaker maintains steady presentation delivery."),
            ("This indicates nervousness and indicates deception.", "this reflects pacing or movement frequency and reflects pacing or movement frequency.")
        ]

        for raw_input, expected_concept in adversarial_texts:
            sanitized = _sanitize_assessment_text(raw_input)
            self.assertNotIn("tone is steady", sanitized.lower())
            self.assertNotIn("conversational tone", sanitized.lower())
            self.assertNotIn("eye contact", sanitized.lower())
            self.assertNotIn("credibility of the claims", sanitized.lower())
            self.assertNotIn("hesitance is noticeable", sanitized.lower())


if __name__ == "__main__":
    unittest.main()
