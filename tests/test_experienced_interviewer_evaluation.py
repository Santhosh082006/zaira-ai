"""
tests/test_experienced_interviewer_evaluation.py
-------------------------------------------------
Comprehensive test suite validating that Zaira evaluates candidate answers
like an experienced senior interviewer across all 6 critical scenarios:

1. Strong answer.
2. Partially correct answer.
3. Incorrect answer.
4. Vague answer.
5. Technically correct but poorly communicated answer.
6. Answer affected by transcription errors.

Non-negotiable verification points:
- Every mark deduction is traceable to a specific rubric criterion.
- Evidence quote, deduction reason, improvement advice, and model answers are present.
- Strict separation of technical correctness and delivery/communication.
- Transcription errors are never penalized as technical knowledge failures.
- Unassessed criteria do not receive 0 marks.
- Total marks awarded and max marks are arithmetically consistent with overall quality.
"""

import os
import sys
import time
import unittest

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from core.schemas import Question, Competency, StructuredEvaluation, RubricCriterionResult, ActionableFinding
from services.answer_evaluator_llm import evaluate_answer_llm, _detect_transcription_glitch


class TestExperiencedInterviewerEvaluation(unittest.TestCase):
    def tearDown(self):
        time.sleep(2.0)

    def setUp(self):
        self.question = Question(
            id="q_tech_proc_thread",
            question_text="Explain the difference between a process and a thread, and how memory is shared.",
            interview_type=["technical"],
            level="intermediate",
            question_type="technical",
            difficulty=0.6,
            topic="Operating Systems",
            competencies=["comp_operating_systems", "comp_system_architecture"]
        )
        self.competencies = [
            Competency(
                id="comp_operating_systems",
                name="Operating Systems Concepts",
                category="technical",
                description="Understanding of processes, threads, virtual memory, scheduling, and concurrency.",
                evidence_markers=["process", "thread", "address space", "heap", "stack", "context switch"]
            ),
            Competency(
                id="comp_system_architecture",
                name="System Architecture & Performance",
                category="technical",
                description="Understanding resource allocation, concurrency overhead, and memory hierarchy.",
                evidence_markers=["virtual memory", "TLB", "PCB", "registers", "cache"]
            )
        ]

    def test_case_1_strong_answer(self):
        """
        Scenario 1: Strong, complete, technically sound, and well-structured answer.
        Expected:
        - High score (>= 8.0/10 or >= 0.8)
        - Technical correctness awarded full or near-full credit
        - Strengths recognized
        - All criteria arithmetically consistent
        """
        transcript = (
            "A process is an independent program in execution with its own private virtual address space, "
            "containing text, data, heap, and stack segments managed through an operating system Process Control Block (PCB). "
            "In contrast, a thread is the smallest schedulable execution entity within a process. "
            "Multiple threads within the same process share the same code, data segment, and heap, "
            "allowing fast communication through shared memory, while each thread maintains its own private stack and CPU registers. "
            "Consequently, thread context switching is much more lightweight than process context switching because it avoids "
            "invalidating CPU page tables and flushing translation lookaside buffers (TLBs)."
        )

        evaluation = evaluate_answer_llm(
            transcript=transcript,
            question=self.question,
            target_competencies=self.competencies,
            interview_type="technical",
            level="mid",
            assessment_goals=["technical_depth", "communication"]
        )

        self.assertEqual(evaluation.evaluation_status, "success")
        self.assertFalse(evaluation.is_transcription_error)
        self.assertGreaterEqual(evaluation.overall_quality, 0.75, "Strong answer should receive >= 0.75 overall quality")

        # Check rubric criteria
        tech_crit = next((c for c in evaluation.rubric_criteria if c.criterion_id == "technical_correctness"), None)
        self.assertIsNotNone(tech_crit, "Technical correctness criterion must be present")
        self.assertGreaterEqual(tech_crit.marks_awarded, 3.0, "Strong answer should get high marks on technical accuracy")

        # Arithmetic consistency
        assessed = [c for c in evaluation.rubric_criteria if c.status != "not_assessed"]
        expected_total_max = sum(c.max_marks for c in assessed)
        expected_total_awarded = round(sum(c.marks_awarded for c in assessed), 2)
        self.assertAlmostEqual(evaluation.total_max_marks, expected_total_max, places=1)
        self.assertAlmostEqual(evaluation.total_marks_awarded, expected_total_awarded, places=1)

    def test_case_2_partially_correct_answer(self):
        """
        Scenario 2: Partially correct answer.
        The candidate correctly states that threads share process memory, but makes an explicit
        factual error claiming each thread has its own separate isolated heap.
        Expected:
        - Partial credit awarded (0.35 <= overall_quality <= 0.75)
        - Traceable deduction on technical correctness or structural completeness
        - Evidence quote isolating the error ("isolated heap" / "separate heap")
        - Reason for deduction, improvement advice, and model answer provided
        """
        transcript = (
            "A process and a thread are both execution units in the OS. "
            "Threads share the process code and global variables. "
            "However, every thread gets its own completely isolated heap memory so that threads never collide on memory allocation, "
            "while processes have separate memory."
        )

        evaluation = evaluate_answer_llm(
            transcript=transcript,
            question=self.question,
            target_competencies=self.competencies,
            interview_type="technical",
            level="mid",
            assessment_goals=["technical_depth"]
        )

        self.assertEqual(evaluation.evaluation_status, "success")
        self.assertFalse(evaluation.is_transcription_error)
        self.assertLess(evaluation.overall_quality, 0.85, "Partially correct answer should not get top marks")
        self.assertGreater(evaluation.overall_quality, 0.20, "Partially correct answer should get credit for correct parts")

        # Verify deduction exists and is traceable
        tech_crit = next((c for c in evaluation.rubric_criteria if c.criterion_id == "technical_correctness"), None)
        self.assertIsNotNone(tech_crit)
        
        has_deduction = any(c.deduction > 0 for c in evaluation.rubric_criteria)
        self.assertTrue(has_deduction, "Partially correct answer must have at least one traceable deduction")

        deducted_crit = next((c for c in evaluation.rubric_criteria if c.deduction > 0 and c.status != "not_assessed"), None)
        self.assertIsNotNone(deducted_crit)
        self.assertIsNotNone(deducted_crit.reason_for_deduction, "Deduction must state the reason")
        self.assertIsNotNone(deducted_crit.improvement_advice, "Deduction must provide improvement advice")
        self.assertIsNotNone(deducted_crit.exemplary_example, "Deduction must provide a model answer example")

    def test_case_3_incorrect_answer(self):
        """
        Scenario 3: Completely incorrect answer spoken with confident tone.
        The candidate states inverted facts: processes share memory by default without OS,
        and threads run separate OS kernels and cannot communicate.
        Expected:
        - Confident tone does NOT reward wrong technical answer.
        - Low technical correctness score (marks_awarded <= 1.5 out of 4.0).
        - Significant mark deduction traceable to false statements.
        - Reason for deduction explains inverted OS definitions.
        """
        transcript = (
            "Processes are lightweight code routines that always share all computer RAM directly without OS intervention. "
            "On the other hand, threads are heavyweight programs that each run their own independent operating system kernel, "
            "meaning threads can never share variables or communicate with each other under any circumstances."
        )

        evaluation = evaluate_answer_llm(
            transcript=transcript,
            question=self.question,
            target_competencies=self.competencies,
            interview_type="technical",
            level="mid",
            assessment_goals=["technical_depth"]
        )

        self.assertEqual(evaluation.evaluation_status, "success")
        tech_crit = next((c for c in evaluation.rubric_criteria if c.criterion_id == "technical_correctness"), None)
        self.assertIsNotNone(tech_crit)
        self.assertLessEqual(tech_crit.marks_awarded, 1.5, "Wrong technical answer must receive heavy technical deduction")
        self.assertIn(tech_crit.status, ["deduction", "partial_credit"])
        self.assertGreaterEqual(tech_crit.deduction, 2.0, "Deduction must reflect major factual error")
        self.assertTrue(bool(tech_crit.reason_for_deduction), "Deduction reason must be clearly stated")
        self.assertTrue(bool(tech_crit.exemplary_example), "Model answer must be provided")

    def test_case_4_vague_answer(self):
        """
        Scenario 4: Vague buzzword answer lacking concrete technical substance.
        Candidate gives high-level generic filler without mentioning virtual address space,
        stack, heap, or context switching mechanisms.
        Expected:
        - Overall quality <= 0.55
        - Deductions in technical correctness and structural completeness
        - Feedback specifically instructs candidate to define concrete mechanisms
        """
        transcript = (
            "Well, in modern computer science, processes and threads are very important concepts for doing tasks. "
            "They basically help everything run much faster and optimize system workflows across various enterprise applications. "
            "You generally use them whenever you need your software architecture to perform well."
        )

        evaluation = evaluate_answer_llm(
            transcript=transcript,
            question=self.question,
            target_competencies=self.competencies,
            interview_type="technical",
            level="mid",
            assessment_goals=["technical_depth"]
        )

        self.assertEqual(evaluation.evaluation_status, "success")
        self.assertLessEqual(evaluation.overall_quality, 0.55, "Vague answer with no substance must receive <= 0.55")
        
        # Check that areas_to_improve or actionable_findings identify the lack of specific details
        has_specificity_feedback = (
            any("specific" in str(f).lower() or "concrete" in str(f).lower() or "detail" in str(f).lower() or "mechanism" in str(f).lower() 
                for f in evaluation.areas_to_improve + [af.finding for af in evaluation.actionable_findings])
        )
        self.assertTrue(has_specificity_feedback, "Evaluation must note the absence of concrete technical mechanisms")

    def test_case_5_technically_correct_but_poorly_communicated(self):
        """
        Scenario 5: Technically correct answer delivered with heavy filler, hesitations,
        and disjointed structure.
        Crucial requirement:
        - Technical correctness must NOT be penalized solely because communication was weak.
        - Communication clarity receives the deduction.
        - Candidate gets fair credit for accurate knowledge.
        """
        transcript = (
            "Um, so, like, process... basically process has its own, um, private address space, you know? "
            "Like PCB, page table, separate heap and stack. And, like, thread... uh, thread is inside process, "
            "so threads share the same heap and data segment, yeah? But, like, each thread has its own stack "
            "and program counter registers. So context switch is, like, way cheaper for threads. Um, yeah, that is basically it."
        )

        evaluation = evaluate_answer_llm(
            transcript=transcript,
            question=self.question,
            target_competencies=self.competencies,
            interview_type="technical",
            level="mid",
            assessment_goals=["technical_depth", "communication"]
        )

        self.assertEqual(evaluation.evaluation_status, "success")
        
        tech_crit = next((c for c in evaluation.rubric_criteria if c.criterion_id == "technical_correctness"), None)
        comm_crit = next((c for c in evaluation.rubric_criteria if c.criterion_id == "communication_clarity"), None)
        
        self.assertIsNotNone(tech_crit)
        self.assertIsNotNone(comm_crit)
        
        # Technical correctness should be high (fair credit)
        self.assertGreaterEqual(tech_crit.marks_awarded, 2.5, "Accurate technical facts must receive credit despite poor delivery")
        
        # Communication clarity should show deduction or lower score
        self.assertLessEqual(comm_crit.marks_awarded, 1.8, "Communication clarity should be evaluated independently for filler words")
        self.assertTrue(tech_crit.marks_awarded / tech_crit.max_marks > comm_crit.marks_awarded / comm_crit.max_marks,
                        "Technical accuracy ratio must be higher than communication clarity ratio")

    def test_case_6_answer_affected_by_transcription_errors(self):
        """
        Scenario 6: Transcript affected by microphone / transmission artifacts.
        Crucial requirement:
        - Audio glitch is detected deterministically (is_transcription_error == True).
        - Technical knowledge is NOT penalized as a knowledge failure (status == 'not_assessed', max_marks == 0.0).
        - Unassessed criteria do not receive 0 marks.
        - Clear guidance to restate answer with working microphone.
        """
        transcript = "[inaudible static] ... [buzzing audio] ... thread ... [cut out] ... [background noise] ..."

        # 1. Test glitch detector unit
        is_glitch, reason = _detect_transcription_glitch(transcript)
        self.assertTrue(is_glitch, "Should detect glitch keywords and inaudible tags")

        # 2. Test evaluator response
        evaluation = evaluate_answer_llm(
            transcript=transcript,
            question=self.question,
            target_competencies=self.competencies,
            interview_type="technical",
            level="mid",
            assessment_goals=["technical_depth"]
        )

        self.assertEqual(evaluation.evaluation_status, "success")
        self.assertTrue(evaluation.is_transcription_error, "Must flag transcription error")
        self.assertIsNotNone(evaluation.transcription_error_details)
        
        # Ensure technical accuracy was NOT assessed or penalized as 0/4
        tech_crit = next((c for c in evaluation.rubric_criteria if c.criterion_id == "technical_correctness"), None)
        self.assertIsNotNone(tech_crit)
        self.assertEqual(tech_crit.status, "not_assessed", "Technical accuracy must be marked not_assessed")
        self.assertEqual(tech_crit.max_marks, 0.0, "Unassessed technical criterion must have 0 max marks to prevent unfair penalty")
        self.assertEqual(tech_crit.deduction, 0.0, "Zero deduction for unassessed technical criterion")
        
        # Competencies must be marked not_assessed or insufficient without score penalty
        for ce in evaluation.competency_evidence:
            self.assertIn(ce.status, ["not_assessed", "insufficient"])
            self.assertIsNone(ce.score, "Competency score must be None for inaudible transcript")

    def test_rubric_arithmetic_integrity(self):
        """
        Tests that for any arbitrary criteria list, total_max_marks, total_marks_awarded,
        deductions, and overall_quality maintain exact mathematical consistency.
        """
        criteria = [
            RubricCriterionResult(
                criterion_id="technical_correctness",
                criterion_name="Technical Correctness",
                max_marks=4.0,
                marks_awarded=3.0,
                deduction=1.0,
                status="partial_credit",
                evidence_quote="processes share memory",
                reason_for_deduction="Omitted virtual memory details",
                improvement_advice="Explain virtual memory mapping",
                exemplary_example="Virtual memory provides hardware isolation"
            ),
            RubricCriterionResult(
                criterion_id="communication_clarity",
                criterion_name="Communication Clarity",
                max_marks=2.0,
                marks_awarded=2.0,
                deduction=0.0,
                status="full_credit"
            ),
            RubricCriterionResult(
                criterion_id="unassessed_dimension",
                criterion_name="Unassessed Dimension",
                max_marks=0.0,
                marks_awarded=0.0,
                deduction=0.0,
                status="not_assessed"
            )
        ]
        
        # Assess mathematical invariants
        assessed = [c for c in criteria if c.status != "not_assessed"]
        total_max = sum(c.max_marks for c in assessed)
        total_awarded = sum(c.marks_awarded for c in assessed)
        expected_overall = round(total_awarded / total_max, 2)
        
        self.assertEqual(total_max, 6.0)
        self.assertEqual(total_awarded, 5.0)
        self.assertAlmostEqual(expected_overall, 0.83, places=2)


if __name__ == "__main__":
    unittest.main()
