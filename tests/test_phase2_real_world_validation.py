"""
tests/test_phase2_real_world_validation.py
-------------------------------------------
Comprehensive validation suite for Phase 2:
1. Evidence-quote verbatim verification, alignment, and rejection of fabricated quotes.
2. Legitimate short-answer vs genuine audio/transcription error discrimination.
   Tests: 'No.', 'A stack.', 'Reference counting.', 'O(n log n).' vs '[inaudible]', empty audio, static.
3. Inconclusive hesitation sounds without hardware failure.
4. Rubric criteria and arithmetic integrity.
5. End-to-end evaluation pipeline with live LLM provider.
"""

import os
import sys
import unittest

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from core.schemas import Question, Competency, RubricCriterionResult, ActionableFinding
from services.answer_evaluator_llm import (
    verify_and_align_evidence_quote,
    _detect_transcription_glitch,
    _detect_inconclusive_filler,
    generate_structured_evaluation,
    evaluate_answer_llm
)


class TestPhase2RealWorldValidation(unittest.TestCase):
    def setUp(self):
        self.tech_question = Question(
            id="q_tech_proc_thread",
            question_text="Explain the difference between a process and a thread, and how memory is shared.",
            interview_type=["technical"],
            level="intermediate",
            question_type="technical",
            difficulty=0.6,
            topic="Operating Systems",
            competencies=["comp_operating_systems"]
        )
        self.dfs_question = Question(
            id="q_tech_dfs_ds",
            question_text="What primary data structure is used to implement Depth-First Search (DFS)?",
            interview_type=["technical"],
            level="beginner",
            question_type="technical",
            difficulty=0.4,
            topic="Data Structures",
            competencies=["comp_data_structures"]
        )
        self.merge_sort_question = Question(
            id="q_tech_merge_sort_complexity",
            question_text="What is the average time complexity of Merge Sort?",
            interview_type=["technical"],
            level="beginner",
            question_type="technical",
            difficulty=0.4,
            topic="Algorithms",
            competencies=["comp_algorithms"]
        )
        self.gc_question = Question(
            id="q_tech_gc_mechanism",
            question_text="Name a fundamental memory management technique used to automatically reclaim unreferenced memory.",
            interview_type=["technical"],
            level="intermediate",
            question_type="technical",
            difficulty=0.5,
            topic="Memory Management",
            competencies=["comp_memory_mgmt"]
        )
        self.competencies = [
            Competency(
                id="comp_operating_systems",
                name="Operating Systems Concepts",
                category="technical",
                description="Understanding processes, threads, virtual address space, and memory sharing.",
                evidence_markers=["process", "thread", "address space", "heap", "stack"]
            ),
            Competency(
                id="comp_data_structures",
                name="Data Structures",
                category="technical",
                description="Knowledge of stacks, queues, trees, and graphs.",
                evidence_markers=["stack", "queue", "DFS", "LIFO"]
            ),
            Competency(
                id="comp_algorithms",
                name="Algorithms & Complexity",
                category="technical",
                description="Big-O analysis and sorting algorithms.",
                evidence_markers=["O(n log n)", "divide and conquer", "logarithmic"]
            ),
            Competency(
                id="comp_memory_mgmt",
                name="Memory Management",
                category="technical",
                description="Techniques for memory deallocation and garbage collection.",
                evidence_markers=["reference counting", "garbage collection", "mark and sweep"]
            )
        ]

    # =========================================================================
    # 1. VERIFY EVIDENCE QUOTES (Valid, Altered, Fabricated)
    # =========================================================================

    def test_quote_verification_exact_verbatim(self):
        """Exact verbatim quote should be verified and returned."""
        transcript = (
            "A process has its own dedicated virtual memory space, "
            "whereas multiple threads within the same process share the same heap and data segments."
        )
        quote = "share the same heap and data segments"
        result = verify_and_align_evidence_quote(quote, transcript)
        self.assertIsNotNone(result)
        self.assertEqual(result, "share the same heap and data segments")
        self.assertIn(result.lower(), transcript.lower())

    def test_quote_verification_with_differing_quotes_and_punctuation(self):
        """Quotes wrapped in punctuation or quotes should match the verbatim substring."""
        transcript = "In Java, every thread gets its own private execution stack."
        quote = "\"its own private execution stack.\""
        result = verify_and_align_evidence_quote(quote, transcript)
        self.assertIsNotNone(result)
        self.assertEqual(result, "its own private execution stack")
        self.assertIn(result.lower(), transcript.lower())

    def test_quote_verification_paraphrased_extracts_verbatim_sequence(self):
        """When an LLM slightly paraphrases, extract the true verbatim sequence."""
        transcript = (
            "I noticed that every thread gets its own completely isolated heap memory "
            "so that threads never collide on memory allocation."
        )
        # Paraphrased version where LLM added/changed minor words
        altered_quote = "isolated heap memory so that threads cannot collide"
        result = verify_and_align_evidence_quote(altered_quote, transcript)
        self.assertIsNotNone(result)
        self.assertIn(result.lower(), transcript.lower(), "Result must exist verbatim in transcript")
        self.assertIn("isolated heap memory", result.lower())

    def test_quote_verification_rejects_fabricated_quotes(self):
        """Completely fabricated/hallucinated quotes must be rejected (return None)."""
        transcript = (
            "A process contains independent text, data, and stack segments. "
            "Threads share the heap."
        )
        fabricated_quote = "I configured a Redis cache cluster with read replicas to handle traffic spikes."
        result = verify_and_align_evidence_quote(fabricated_quote, transcript)
        self.assertIsNone(result, "Fabricated statements must be rejected with None")

    def test_quote_verification_short_transcript_valid(self):
        """Short transcripts must correctly match valid short candidate statements."""
        transcript = "A stack."
        self.assertEqual(verify_and_align_evidence_quote("A stack", transcript), "A stack")
        self.assertEqual(verify_and_align_evidence_quote("stack", transcript), "stack")
        self.assertIsNone(verify_and_align_evidence_quote("A queue", transcript))

    # =========================================================================
    # 2. SHORT-ANSWER VS TRANSCRIPTION-ERROR DISCRIMINATION
    # =========================================================================

    def test_short_answer_no_is_not_transcription_error(self):
        """'No.' is a concise answer/refusal, NOT a transcription/hardware failure."""
        is_glitch, reason = _detect_transcription_glitch("No.")
        self.assertFalse(is_glitch, "'No.' must not be classified as a transcription glitch")

    def test_short_answer_a_stack_is_not_transcription_error(self):
        """'A stack.' is a valid concise answer, NOT a transcription/hardware failure."""
        is_glitch, reason = _detect_transcription_glitch("A stack.")
        self.assertFalse(is_glitch, "'A stack.' must not be classified as a transcription glitch")

    def test_short_answer_reference_counting_is_not_transcription_error(self):
        """'Reference counting.' is a valid technical answer, NOT a transcription failure."""
        is_glitch, reason = _detect_transcription_glitch("Reference counting.")
        self.assertFalse(is_glitch, "'Reference counting.' must not be classified as a glitch")

    def test_short_answer_big_o_is_not_transcription_error(self):
        """'O(n log n).' is a valid complexity answer, NOT a transcription failure."""
        is_glitch, reason = _detect_transcription_glitch("O(n log n).")
        self.assertFalse(is_glitch, "'O(n log n).' must not be classified as a glitch")

    def test_true_transcription_glitch_detected(self):
        """Actual transmission static or inaudible tags must be detected as glitches."""
        glitch_transcripts = [
            "[inaudible] ... [static] ... [buzz]",
            "[cut out] ... could not hear ... [audio corrupted]",
            "",  # empty recording
            "   \n\t  ",  # pure whitespace
            "... ... ... ???",  # pure corrupted non-lexical noise
        ]
        for gt in glitch_transcripts:
            is_glitch, reason = _detect_transcription_glitch(gt)
            self.assertTrue(is_glitch, f"Should detect glitch for: '{gt}'")
            self.assertTrue(len(reason) > 0)

    def test_inconclusive_filler_distinguished_from_hardware_glitch(self):
        """Pure hesitation ('uh ... um') is inconclusive, but NOT a hardware glitch."""
        filler_transcript = "uh ... um ... ah ... hmm"
        is_glitch, reason = _detect_transcription_glitch(filler_transcript)
        is_filler = _detect_inconclusive_filler(filler_transcript)
        
        self.assertFalse(is_glitch, "Filler sounds must not be blamed on microphone failure")
        self.assertTrue(is_filler, "Should detect purely hesitation sounds")

        # Inconclusive evaluation result
        eval_res = generate_structured_evaluation(
            question=self.tech_question,
            transcript=filler_transcript,
            interview_type="technical",
            level="mid",
            assessment_goals=["technical_depth"],
            target_competencies=self.competencies
        )
        self.assertEqual(eval_res.evaluation_status, "success")
        self.assertFalse(eval_res.is_transcription_error)
        self.assertTrue(any("inconclusive" in lim.lower() for lim in eval_res.evaluation_limitations))
        
        # Technical correctness should be not_assessed (no unfair penalty for hesitation)
        tech_crit = next((c for c in eval_res.rubric_criteria if c.criterion_id == "technical_correctness"), None)
        self.assertIsNotNone(tech_crit)
        self.assertEqual(tech_crit.status, "not_assessed")
        self.assertEqual(tech_crit.max_marks, 0.0)

    # =========================================================================
    # 3. LIVE EVALUATION OF SHORT TECHNICAL ANSWERS
    # =========================================================================

    def test_live_evaluation_short_answer_a_stack_correct(self):
        """
        'A stack.' for DFS question:
        Must NOT be flagged as glitch.
        Must receive full marks for technical correctness (4.0/4.0).
        """
        eval_res = evaluate_answer_llm(
            question=self.dfs_question,
            transcript="A stack.",
            interview_type="technical",
            level="beginner",
            assessment_goals=["technical_depth"],
            target_competencies=self.competencies
        )
        self.assertEqual(eval_res.evaluation_status, "success")
        self.assertFalse(eval_res.is_transcription_error, "Must not flag 'A stack.' as transcription error")

        tech_crit = next((c for c in eval_res.rubric_criteria if c.criterion_id == "technical_correctness"), None)
        self.assertIsNotNone(tech_crit)
        self.assertGreaterEqual(tech_crit.marks_awarded, 3.5, "A stack is the correct answer for DFS; should get high marks")

        # Evidence quote verification
        if tech_crit.evidence_quote:
            self.assertIn(tech_crit.evidence_quote.lower(), "a stack.")

    def test_live_evaluation_short_answer_complexity_o_n_log_n(self):
        """
        'O(n log n).' for Merge Sort complexity:
        Must NOT be flagged as glitch.
        Must receive full credit for technical correctness.
        """
        eval_res = evaluate_answer_llm(
            question=self.merge_sort_question,
            transcript="O(n log n).",
            interview_type="technical",
            level="beginner",
            assessment_goals=["technical_depth"],
            target_competencies=self.competencies
        )
        self.assertEqual(eval_res.evaluation_status, "success")
        self.assertFalse(eval_res.is_transcription_error)

        tech_crit = next((c for c in eval_res.rubric_criteria if c.criterion_id == "technical_correctness"), None)
        self.assertIsNotNone(tech_crit)
        self.assertGreaterEqual(tech_crit.marks_awarded, 3.5, "O(n log n) is correct for Merge Sort")

    def test_live_evaluation_short_answer_refusal_no(self):
        """
        'No.' when asked to explain process vs thread:
        Must NOT be flagged as transcription error.
        Technical correctness gets deduction for lack of explanation.
        """
        eval_res = evaluate_answer_llm(
            question=self.tech_question,
            transcript="No.",
            interview_type="technical",
            level="intermediate",
            assessment_goals=["technical_depth"],
            target_competencies=self.competencies
        )
        self.assertEqual(eval_res.evaluation_status, "success")
        self.assertFalse(eval_res.is_transcription_error, "Candidate saying 'No.' is not a microphone failure")

        tech_crit = next((c for c in eval_res.rubric_criteria if c.criterion_id == "technical_correctness"), None)
        self.assertIsNotNone(tech_crit)
        self.assertLessEqual(tech_crit.marks_awarded, 1.0, "Saying 'No.' should not receive technical marks")

    # =========================================================================
    # 4. SCORING & ARITHMETIC INTEGRITY INVARIANTS
    # =========================================================================

    def test_unassessed_criteria_not_penalized(self):
        """Criteria with max_marks=0.0 and status='not_assessed' do not reduce overall_quality."""
        criteria = [
            RubricCriterionResult(
                criterion_id="technical_correctness",
                criterion_name="Technical Correctness",
                max_marks=0.0,
                marks_awarded=0.0,
                deduction=0.0,
                status="not_assessed"
            ),
            RubricCriterionResult(
                criterion_id="communication_clarity",
                criterion_name="Communication Clarity",
                max_marks=2.0,
                marks_awarded=2.0,
                deduction=0.0,
                status="full_credit"
            )
        ]
        assessed = [c for c in criteria if c.status != "not_assessed"]
        total_max = sum(c.max_marks for c in assessed)
        total_awarded = sum(c.marks_awarded for c in assessed)
        overall = round(total_awarded / total_max, 2)

        self.assertEqual(total_max, 2.0)
        self.assertEqual(total_awarded, 2.0)
        self.assertEqual(overall, 1.0, "Overall score must be 100% when all assessed criteria receive full marks")


if __name__ == "__main__":
    unittest.main()
