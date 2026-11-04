from typing import Optional, List, Dict
from core.schemas import (
    InterviewState, AnswerRecord, NextQuestionDecision, Question
)
from core.question_bank import QuestionBank
from core.competency_map import CompetencyMap

class AdaptiveInterviewController:
    def __init__(self, question_bank: QuestionBank, competency_map: CompetencyMap):
        self.qb = question_bank
        self.cm = competency_map
        
        # Safety limits and configurations
        self.MAX_QUESTIONS = 7
        self.MIN_QUESTIONS = 3
        self.MAX_CONSECUTIVE_CLARIFICATIONS = 2
        
        # Difficulty calibration thresholds
        self.STRONG_ANSWER_THRESHOLD = 0.8
        self.WEAK_ANSWER_THRESHOLD = 0.4
        self.DIFFICULTY_STEP = 0.1
        
    def _is_finalize(self, state: InterviewState) -> tuple[bool, str]:
        """
        Returns (should_finalize, reason).
        Authoritative source for finalization is competency_coverage, NOT question history.
        """
        if len(state.question_history) >= self.MAX_QUESTIONS:
            return True, "Safety maximum question limit reached."
            
        if not state.assessment_goals:
            return False, ""
            
        if len(state.question_history) < self.MIN_QUESTIONS:
            return False, ""
            
        # Determine if all required competencies are demonstrated
        # We look at coverage rather than missing/tested lists.
        # If coverage dict is empty, we haven't started.
        if not state.competency_coverage:
            return False, ""
            
        all_demonstrated = True
        for comp_id, cov_data in state.competency_coverage.items():
            status = cov_data.get("status") if isinstance(cov_data, dict) else getattr(cov_data, "status", "not_tested")
            if status != "demonstrated":
                all_demonstrated = False
                break
                
        if all_demonstrated:
            return True, "All targeted competencies successfully demonstrated."
            
        return False, ""

    def _get_consecutive_clarifications(self, state: InterviewState) -> int:
        count = 0
        for log in reversed(state.controller_history):
            if log.decision == "clarification":
                count += 1
            else:
                break
        return count

    def _find_best_question(self, 
                            state: InterviewState, 
                            question_type: Optional[str] = None, 
                            target_competency: Optional[str] = None,
                            difficulty_range: float = 0.5) -> Optional[Question]:
        """
        Uses QuestionBank to find an eligible question avoiding duplicates.
        """
        eligible = self.qb.filter_questions(
            interview_type=state.interview_type,
            level=state.interview_level,
            exclude_ids=state.question_history,
            technical_domain=state.technical_domain,
            target_competency=target_competency,
            question_type=question_type
        )
        
        if not eligible:
            # Fallback: remove question_type constraint
            eligible = self.qb.filter_questions(
                interview_type=state.interview_type,
                level=state.interview_level,
                exclude_ids=state.question_history,
                technical_domain=state.technical_domain,
                target_competency=target_competency
            )
            
        if not eligible:
            # Fallback: remove target_competency constraint
            eligible = self.qb.filter_questions(
                interview_type=state.interview_type,
                level=state.interview_level,
                exclude_ids=state.question_history,
                technical_domain=state.technical_domain
            )
            
        if not eligible and state.technical_domain:
            # Fallback: remove technical_domain constraint
            eligible = self.qb.filter_questions(
                interview_type=state.interview_type,
                level=state.interview_level,
                exclude_ids=state.question_history
            )
            
        if not eligible:
            # Fallback: relax level constraint
            for alt_level in ["intermediate", "beginner", "advanced"]:
                if alt_level != state.interview_level:
                    eligible = self.qb.filter_questions(
                        interview_type=state.interview_type,
                        level=alt_level,
                        exclude_ids=state.question_history
                    )
                    if eligible:
                        break

        if not eligible:
            # Fallback: relax interview_type to any remaining unasked question
            eligible = [q for q in self.qb.questions if q.id not in state.question_history]
            
        if not eligible:
            return None
            
        # Select closest difficulty with variety/randomization among top candidates
        eligible.sort(key=lambda q: abs(q.difficulty - difficulty_range))
        best_diff = abs(eligible[0].difficulty - difficulty_range)
        top_candidates = [q for q in eligible if abs(abs(q.difficulty - difficulty_range) - best_diff) <= 0.15]
        
        import random
        return random.choice(top_candidates)

    def determine_next_action(self, state: InterviewState, latest_answer: Optional[AnswerRecord]) -> NextQuestionDecision:
        """
        Core decision loop.
        Priority:
        1. FINALIZE
        2. CLARIFICATION
        3. FOLLOW_UP / DEEPER PROBE
        4. MISSING COMPETENCY
        5. NEW TOPIC
        """
        
        # --- 1. INITIAL QUESTION (No history) ---
        if not latest_answer and not state.question_history:
            q = self._find_best_question(state, question_type="introduction")
            if not q:
                q = self._find_best_question(state) # Fallback
            
            return NextQuestionDecision(
                next_question_id=q.id if q else None,
                decision_type="new_topic",
                reason="Initial interview question.",
                target_competencies=q.competencies if q else [],
                difficulty_change=0.0
            )

        # --- 2. FINALIZE ---
        should_finalize, finalize_reason = self._is_finalize(state)
        if should_finalize:
            return NextQuestionDecision(
                next_question_id=None,
                decision_type="finalize",
                reason=finalize_reason,
                difficulty_change=0.0
            )

        # Calculate difficulty shift
        diff_change = 0.0
        if latest_answer and latest_answer.overall_answer_quality is not None:
            if latest_answer.overall_answer_quality > self.STRONG_ANSWER_THRESHOLD:
                diff_change = self.DIFFICULTY_STEP
            elif latest_answer.overall_answer_quality < self.WEAK_ANSWER_THRESHOLD:
                diff_change = -self.DIFFICULTY_STEP
                
        target_diff = max(0.0, min(1.0, state.current_difficulty + diff_change))

        # --- 3. CLARIFICATION ---
        if latest_answer and latest_answer.overall_answer_quality is not None and latest_answer.overall_answer_quality < 0.3:
            if self._get_consecutive_clarifications(state) < self.MAX_CONSECUTIVE_CLARIFICATIONS:
                q = self._find_best_question(state, question_type="clarification", difficulty_range=target_diff)
                return NextQuestionDecision(
                    next_question_id=q.id if q else None,
                    decision_type="clarification",
                    reason="Previous answer was incomplete or low quality.",
                    target_competencies=q.competencies if q else (state.competencies_missing[:1] or ["comm_clarity"]),
                    difficulty_change=diff_change
                )

        # --- 4. FOLLOW UP / DEEPER PROBE ---
        # If the latest answer had interesting unexplored claims
        if latest_answer and latest_answer.detected_claims:
            q = self._find_best_question(state, question_type="follow_up", difficulty_range=target_diff)
            return NextQuestionDecision(
                next_question_id=q.id if q else None,
                decision_type="follow_up",
                reason="Probing unexplored claims from previous answer.",
                target_competencies=q.competencies if q else (state.competencies_missing[:1] or ["tech_technical_depth"]),
                difficulty_change=diff_change
            )

        # If a competency was just tested but evidence is weak
        if latest_answer and state.competencies_tested:
            last_tested = state.competencies_tested[-1]
            cov = state.competency_coverage.get(last_tested)
            
            # Extract status safely whether dict or Pydantic object
            cov_status = "not_tested"
            if cov:
                cov_status = cov.get("status") if isinstance(cov, dict) else getattr(cov, "status", "not_tested")
                
            if cov_status in ["insufficient_evidence", "developing", "partially_demonstrated", "needs_improvement"]:
                # Deeper probe needed
                q = self._find_best_question(state, target_competency=last_tested, difficulty_range=target_diff)
                return NextQuestionDecision(
                    next_question_id=q.id if q else None,
                    decision_type="deeper_probe",
                    reason=f"Competency {last_tested} needs more evidence.",
                    target_competencies=q.competencies if q else [last_tested],
                    difficulty_change=diff_change
                )

        # --- 5. MISSING COMPETENCY ---
        if state.competencies_missing:
            target_comp = state.competencies_missing[0]
            q = self._find_best_question(state, target_competency=target_comp, difficulty_range=target_diff)
            return NextQuestionDecision(
                next_question_id=q.id if q else None,
                decision_type="missing_competency",
                reason=f"Targeting missing competency: {target_comp}.",
                target_competencies=q.competencies if q else [target_comp],
                difficulty_change=diff_change
            )

        # --- 6. TARGET WEAKNESS (Optional fallback) ---
        if latest_answer and latest_answer.detected_weaknesses:
            # We just get any new question
            pass 

        # --- 7. NEW TOPIC (Fallback) ---
        q = self._find_best_question(state, difficulty_range=target_diff)
        return NextQuestionDecision(
            next_question_id=q.id if q else None,
            decision_type="new_topic",
            reason="Moving to new topic as current competencies are satisfied.",
            target_competencies=q.competencies if q else (state.competencies_missing[:1] or ["comm_relevance"]),
            difficulty_change=diff_change
        )

        # If we reach here and have NO questions left at all
        return NextQuestionDecision(
            next_question_id=None,
            decision_type="finalize",
            reason="Question bank exhausted.",
            difficulty_change=0.0
        )
