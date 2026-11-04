"""
tests/test_ollama_integration.py
─────────────────────────────────────────────────────────────────────────────
Local Ollama Integration Tests for TruthLens AI / Zaira.

Validates:
1. Basic model response via call_llm
2. Structured JSON generation via Ollama format constraint
3. Interview answer evaluation using qwen2.5:7b
4. Adaptive follow-up question generation using qwen2.5:7b
5. Provider unavailable / connection error handling (never fabricates marks)
6. Model not found (HTTP 404) error handling
"""

import os
import unittest
import json
from unittest.mock import patch

from services.llm_provider import call_llm, get_active_provider
from core.schemas import Question, Competency, InterviewState, NextQuestionDecision, AnswerRecord
from services.answer_evaluator_llm import generate_structured_evaluation
from services.question_generator_llm import generate_adaptive_question, generate_fallback_question


class TestOllamaIntegration(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # Configure local Ollama environment for testing
        os.environ["LLM_PROVIDER"] = "ollama"
        os.environ["OLLAMA_MODEL"] = "qwen2.5:7b"
        os.environ["OLLAMA_BASE_URL"] = "http://localhost:11434"
        os.environ["OLLAMA_TIMEOUT"] = "300"
        os.environ.pop("TEST_MOCK_LLM", None)

    def test_01_active_provider_and_basic_response(self):
        """Verify provider resolution and basic response from local qwen2.5:7b."""
        self.assertEqual(get_active_provider(), "ollama")
        response = call_llm("Respond with the single word: OK", system_prompt="You are a helpful assistant.")
        self.assertIsInstance(response, str)
        self.assertTrue(len(response.strip()) > 0)
        self.assertIn("ok", response.lower())

    def test_02_structured_json_output(self):
        """Verify that Ollama enforces valid JSON when requested in prompt/system."""
        prompt = "Return a JSON object with keys 'status' and 'test_id'. Set status to 'active' and test_id to 42."
        system_prompt = "You are a test evaluator. Output valid raw JSON only."
        response = call_llm(prompt=prompt, system_prompt=system_prompt)
        self.assertIsInstance(response, str)
        
        # Verify strict JSON parsing
        try:
            data = json.loads(response.strip())
        except json.JSONDecodeError as e:
            self.fail(f"Ollama response was not valid JSON: {response}")
            
        self.assertEqual(data.get("status"), "active")
        self.assertEqual(data.get("test_id"), 42)

    def test_03_interview_answer_evaluation(self):
        """Verify full structured answer evaluation with qwen2.5:7b."""
        question = Question(
            id="q_test_jvm",
            question_text="How does Garbage Collection manage memory in Java?",
            interview_type=["technical"],
            level="intermediate",
            topic="jvm_memory",
            difficulty=0.6,
            question_type="technical",
            competencies=["tech_technical_explanation"],
            follow_up_tags=["gc"],
            expected_answer_characteristics=["mentions heap", "generational hypothesis"]
        )

        competency = Competency(
            id="tech_technical_explanation",
            name="Technical Explanation",
            description="Explains technical mechanisms clearly and accurately",
            category="technical",
            evidence_markers=["explains mechanisms", "correct terminology"]
        )

        transcript = (
            "In Java, garbage collection automatically manages heap memory. "
            "It uses a generational hypothesis with Eden, Survivor, and Tenured spaces. "
            "Objects that are unreachable from GC roots are marked and swept during minor or major collections."
        )

        evaluation = generate_structured_evaluation(
            question=question,
            transcript=transcript,
            interview_type="technical",
            level="intermediate",
            assessment_goals=["Evaluate JVM memory knowledge"],
            target_competencies=[competency]
        )

        # 1. Verification of evaluation status
        self.assertEqual(evaluation.evaluation_status, "success")
        self.assertFalse(evaluation.is_transcription_error)

        # 2. Rubric criteria and arithmetic integrity
        self.assertTrue(len(evaluation.rubric_criteria) >= 4)
        assessed = [c for c in evaluation.rubric_criteria if c.status != "not_assessed"]
        self.assertAlmostEqual(evaluation.total_marks_awarded, sum(c.marks_awarded for c in assessed), places=2)
        self.assertAlmostEqual(evaluation.total_max_marks, sum(c.max_marks for c in assessed), places=2)

        # 3. Evidence quotes must be verbatim substrings of transcript
        for c in evaluation.rubric_criteria:
            if c.evidence_quote:
                self.assertIn(c.evidence_quote.lower(), transcript.lower())

    def test_04_adaptive_follow_up_question_generation(self):
        """Verify adaptive follow-up question generation tailored to candidate's answer."""
        state = InterviewState(
            session_id="sess_ollama_test",
            interview_type="technical",
            interview_level="intermediate",
            technical_domain="Java",
            assessment_goals=["tech_technical_explanation"]
        )

        decision = NextQuestionDecision(
            decision_type="follow_up",
            reason="Candidate explained generational memory; probe deeper into how objects age into tenured space.",
            target_competencies=["tech_technical_explanation"]
        )

        latest_answer = AnswerRecord(
            answer_id="ans_test_01",
            session_id="sess_ollama_test",
            question_id="q_test_jvm",
            transcript="In Java, garbage collection uses Eden, Survivor, and Tenured spaces.",
            detected_claims=["uses Eden", "uses Survivor", "uses Tenured spaces"],
            media_reference="ref_test",
            duration=12.0
        )

        gen_question = generate_adaptive_question(
            state=state,
            decision=decision,
            latest_answer=latest_answer,
            target_competency="tech_technical_explanation",
            previous_question_text="How does Garbage Collection manage memory in Java?"
        )

        self.assertIsNotNone(gen_question)
        self.assertIsInstance(gen_question, Question)
        self.assertEqual(gen_question.technical_domain, "Java")
        self.assertEqual(gen_question.question_type, "technical")
        
        # Single question rule
        self.assertEqual(gen_question.question_text.count("?"), 1)
        # Grounded in candidate's context
        q_lower = gen_question.question_text.lower()
        self.assertTrue(any(term in q_lower for term in ("survivor", "tenured", "eden", "generation", "garbage", "object", "memory")))

    def test_05_provider_unavailable_handling(self):
        """Verify that when Ollama is unavailable, errors are explicit and scores are NOT fabricated."""
        with patch.dict(os.environ, {"OLLAMA_BASE_URL": "http://127.0.0.1:59999"}):
            # 1. call_llm raises descriptive RuntimeError
            with self.assertRaises(RuntimeError) as ctx:
                call_llm("Ping")
            self.assertIn("Ollama connection failed", str(ctx.exception))

            # 2. answer_evaluator_llm marks unavailable without fabricating marks
            dummy_q = Question(
                id="q_fail",
                question_text="Dummy question",
                interview_type=["technical"],
                level="intermediate",
                topic="test",
                difficulty=0.5,
                question_type="technical",
                competencies=[],
                follow_up_tags=[],
                expected_answer_characteristics=[]
            )
            eval_res = generate_structured_evaluation(
                question=dummy_q,
                transcript="Some candidate answer",
                interview_type="technical",
                level="intermediate",
                assessment_goals=[],
                target_competencies=[]
            )
            self.assertEqual(eval_res.evaluation_status, "unavailable")
            self.assertEqual(eval_res.total_marks_awarded, 0.0)
            self.assertTrue(len(eval_res.evaluation_limitations) > 0)
            self.assertTrue(any("Ollama" in lim or "unavailable" in lim for lim in eval_res.evaluation_limitations))

            # 3. question_generator_llm returns None so fallback can be invoked
            state = InterviewState(
                session_id="sess_err",
                interview_type="technical",
                interview_level="intermediate",
                technical_domain="Java",
                assessment_goals=["tech_technical_explanation"]
            )
            decision = NextQuestionDecision(decision_type="follow_up", reason="test")
            q_res = generate_adaptive_question(state=state, decision=decision)
            self.assertIsNone(q_res)

            # Controller fallback question works deterministically
            fb_q = generate_fallback_question(state=state, decision=decision)
            self.assertIsNotNone(fb_q)
            self.assertEqual(fb_q.technical_domain, "Java")

    def test_06_model_not_found_handling(self):
        """Verify that requesting a missing model raises a clear 404 error."""
        with patch.dict(os.environ, {"OLLAMA_MODEL": "non_existent_model_truthlens_xyz"}):
            with self.assertRaises(RuntimeError) as ctx:
                call_llm("Ping")
            self.assertIn("not found", str(ctx.exception).lower())


if __name__ == "__main__":
    unittest.main()
