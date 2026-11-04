import uuid
import json
import os
import threading
from typing import Optional, Dict, Any, Tuple, List

from core.schemas import InterviewState, Question, AnswerRecord, NextQuestionDecision
from core.question_bank import QuestionBank
from core.competency_map import CompetencyMap
from core.interview_controller import AdaptiveInterviewController
from core.answer_evaluator import AnswerEvaluator

class InterviewSessionService:
    def __init__(self, checkpoint_dir: str = ".sessions"):
        self.qb = QuestionBank()
        self.cm = CompetencyMap()
        self.controller = AdaptiveInterviewController(self.qb, self.cm)
        self.evaluator = AnswerEvaluator(self.cm)
        self.checkpoint_dir = checkpoint_dir
        
        if not os.path.exists(self.checkpoint_dir):
            os.makedirs(self.checkpoint_dir)
            
        self.active_sessions: Dict[str, InterviewState] = {}
        self.answer_records: Dict[str, AnswerRecord] = {}
        self.retry_originals: Dict[str, AnswerRecord] = {}
        self.revision_deltas: Dict[str, Dict[str, Any]] = {}
        self._session_locks: Dict[str, threading.RLock] = {}
        self._global_lock = threading.Lock()
        
    def _get_session_lock(self, session_id: str) -> threading.RLock:
        with self._global_lock:
            if session_id not in self._session_locks:
                self._session_locks[session_id] = threading.RLock()
            return self._session_locks[session_id]

    def _resolve_next_question(
        self,
        state: InterviewState,
        decision: NextQuestionDecision,
        latest_answer: Optional[AnswerRecord] = None
    ) -> Optional[Question]:
        """
        Coordinates dynamic question generation with domain-safe fallback.
        Preserves controller authority while ensuring domain relevance and grounding.
        """
        if decision.decision_type == "finalize":
            return None

        from services.question_generator_llm import generate_adaptive_question, generate_fallback_question

        # 1. Determine target competency
        target_comp = None
        if decision.target_competencies:
            target_comp = decision.target_competencies[0]
        elif state.competencies_missing:
            target_comp = state.competencies_missing[0]
        elif state.assessment_goals:
            target_comp = state.assessment_goals[0]

        # 2. Context from previous questions
        prev_q_text = None
        if state.current_question_id:
            prev_q = self.qb.get_question_by_id(state.current_question_id)
            if prev_q:
                prev_q_text = prev_q.question_text

        history_texts = []
        for qid in state.question_history:
            q_hist = self.qb.get_question_by_id(qid)
            if q_hist and q_hist.question_text:
                history_texts.append(q_hist.question_text)

        # Fast-path for opening question (no candidate answer yet):
        # Use the controller-selected QuestionBank question or curated domain question immediately
        # to avoid a 90+ second local LLM inference delay right at session launch.
        if not latest_answer:
            if decision.next_question_id:
                cand_q = self.qb.get_question_by_id(decision.next_question_id)
                if cand_q:
                    if not state.technical_domain or (cand_q.technical_domain and cand_q.technical_domain.lower() == state.technical_domain.lower()):
                        return cand_q

            # If no bank question directly matched the technical domain/level, use curated domain question immediately
            fb_q = generate_fallback_question(
                state=state,
                decision=decision,
                latest_answer=None,
                target_competency=target_comp
            )
            if fb_q:
                self.qb.add_question(fb_q)
                decision.next_question_id = fb_q.id
                return fb_q

        # 3. Attempt LLM generation
        dyn_q = None
        try:
            dyn_q = generate_adaptive_question(
                state=state,
                decision=decision,
                latest_answer=latest_answer,
                target_competency=target_comp,
                previous_question_text=prev_q_text,
                question_history_texts=history_texts
            )
        except Exception:
            dyn_q = None

        if dyn_q:
            self.qb.add_question(dyn_q)
            decision.next_question_id = dyn_q.id
            return dyn_q

        # 4. Check if bank question exists and matches domain
        cand_q = None
        if decision.next_question_id:
            cand_q = self.qb.get_question_by_id(decision.next_question_id)

        if cand_q and state.technical_domain:
            # If bank question does not match technical domain, do NOT use generic behavioral!
            if not cand_q.technical_domain or cand_q.technical_domain.lower() != state.technical_domain.lower():
                cand_q = None

        if cand_q:
            return cand_q

        # 5. Fallback: Deterministic domain-safe fallback
        fb_q = generate_fallback_question(
            state=state,
            decision=decision,
            latest_answer=latest_answer,
            target_competency=target_comp
        )
        self.qb.add_question(fb_q)
        decision.next_question_id = fb_q.id
        return fb_q

    def start_interview(
        self,
        interview_type: str,
        interview_level: str,
        assessment_goals: List[str],
        technical_domain: Optional[str] = None,
        custom_goal: Optional[str] = None
    ) -> Tuple[InterviewState, Optional[Question]]:
        
        session_id = f"sess_{uuid.uuid4().hex[:12]}"
        
        # Normalize interview_type and level
        type_norm = (interview_type or "job").lower().strip()
        if "placement" in type_norm or "job" in type_norm:
            canonical_type = "job"
        elif "hr" in type_norm:
            canonical_type = "hr"
        elif "tech" in type_norm:
            canonical_type = "technical"
        elif "eng" in type_norm:
            canonical_type = "english"
        elif "custom" in type_norm:
            canonical_type = "custom"
        else:
            canonical_type = type_norm
            
        canonical_level = (interview_level or "intermediate").lower().strip()

        # Flatten categories into specific competency IDs if needed
        target_competencies = []
        for goal in assessment_goals:
            # check if goal is a direct competency ID
            if self.cm.get_competency_by_id(goal):
                target_competencies.append(goal)
            else:
                # assume it's a category
                for c in self.cm.competencies:
                    if c.category == goal or c.category.upper() == goal.upper():
                        target_competencies.append(c.id)
                        
        target_competencies = list(set(target_competencies))
        if not target_competencies:
            # Fallback to default core communication competencies
            target_competencies = ["comm_clarity", "comm_relevance", "perf_confidence_delivery"]
        
        state = InterviewState(
            session_id=session_id,
            interview_type=canonical_type,
            interview_level=canonical_level,
            assessment_goals=target_competencies, # Set goals as explicit IDs for controller processing
            technical_domain=technical_domain,
            custom_goal=custom_goal,
            competencies_missing=list(target_competencies)
        )
        
        # Initialize coverage
        coverage_models = self.cm.initialize_coverage_model(target_competencies)
        for model in coverage_models:
            state.competency_coverage[model.competency_id] = model
            
        # Get first question
        decision = self.controller.determine_next_action(state, latest_answer=None)
        
        question = self._resolve_next_question(state, decision, latest_answer=None)
        if decision.decision_type == "finalize" or not question:
            state.completion_status = "completed"
            state.current_question_id = None
        else:
            state.current_question_id = question.id
            state.question_history.append(question.id)
            
        # Add to state and save checkpoint
        self.active_sessions[session_id] = state
        self._save_checkpoint(state)
        
        return state, question

    def process_media_answer(
        self,
        session_id: str,
        question_id: str,
        media_path: str,
        media_type: str,
        media_processor: Any # Pass in MediaProcessor instance
    ) -> Tuple[InterviewState, Optional[Question], AnswerRecord, NextQuestionDecision]:
        """
        Process a real audio/video file.
        Fails safely without mutating InterviewState.
        """
        if media_type not in ["audio", "video"]:
            raise ValueError("media_type must be 'audio' or 'video'")
            
        # 1. Execute heavy synchronous media pipeline (outside of session transaction)
        if media_type == "audio":
            analysis = media_processor.process_audio(media_path)
        else:
            analysis = media_processor.process_video(media_path)
            
        # 2. Delegate to the standard processing pipeline within the safety of the transaction
        return self.process_candidate_answer(
            session_id=session_id,
            question_id=question_id,
            transcript=analysis.transcript,
            content_analysis=analysis.content_analysis,
            speech_metrics=analysis.speech_metrics,
            visual_metrics=analysis.visual_metrics,
            language_metrics=analysis.language_metrics,
            duration=analysis.duration,
            media_reference=analysis.media_reference
        )

    def process_candidate_answer(
        self,
        session_id: str,
        question_id: str,
        transcript: str,
        content_analysis: Dict[str, Any],
        speech_metrics: Optional[Dict[str, float]] = None,
        visual_metrics: Optional[Dict[str, float]] = None,
        language_metrics: Optional[Dict[str, float]] = None,
        duration: float = 0.0,
        media_reference: str = ""
    ) -> Tuple[InterviewState, Optional[Question], AnswerRecord, NextQuestionDecision]:
        
        with self._get_session_lock(session_id):
            state = self.get_session(session_id)
            if not state:
                raise ValueError(f"Invalid session ID: {session_id}")
                
            if state.completion_status == "completed":
                raise ValueError("Session is already completed.")
                
            if state.current_question_id != question_id:
                raise ValueError(f"Wrong question ID. Expected {state.current_question_id}, got {question_id}")
                
            question = self.qb.get_question_by_id(question_id)
            if not question:
                raise ValueError(f"Question {question_id} not found in QuestionBank.")
            
            if not transcript or not transcript.strip():
                raise ValueError("No speech detected. Please speak clearly and try again.")
            
            import copy
            working_state = copy.deepcopy(state)
            
            # Evaluate Answer
            working_state, record = self.evaluator.process_answer(
                state=working_state,
                question=question,
                transcript=transcript,
                content_analysis=content_analysis,
                speech_metrics=speech_metrics,
                visual_metrics=visual_metrics,
                language_metrics=language_metrics,
                duration=duration,
                media_reference=media_reference
            )
            
            # Check if this answer is a retry revision
            key = f"{session_id}_{question_id}"
            revision_delta = None
            if key in self.retry_originals:
                original_rec = self.retry_originals[key]
                record.is_revision = True
                record.revision_target_answer_id = original_rec.answer_id
                revision_delta = self.compare_answer_revision(original_rec, record)
                self.revision_deltas[record.answer_id] = revision_delta
                del self.retry_originals[key]

            # Cache latest record
            self.answer_records[record.answer_id] = record
            self.answer_records[f"{session_id}_{question_id}_latest"] = record

            # Check Evaluation Status
            if record.structured_evaluation and record.structured_evaluation.evaluation_status != "success":
                # Rollback: Do not save working_state. Do not advance.
                reason = record.structured_evaluation.evaluation_limitations[0] if record.structured_evaluation.evaluation_limitations else "Evaluation failed."
                from core.schemas import NextQuestionDecision
                decision = NextQuestionDecision(
                    next_question_id=state.current_question_id,
                    decision_type=f"evaluation_{record.structured_evaluation.evaluation_status}",
                    reason=reason
                )
                return state, question, record, decision
            
            # Determine Next Action
            decision = self.controller.determine_next_action(working_state, latest_answer=record)
            
            next_question = self._resolve_next_question(working_state, decision, latest_answer=record)
            if decision.decision_type == "finalize" or not next_question:
                working_state.completion_status = "completed"
                working_state.current_question_id = None
            else:
                working_state.current_question_id = next_question.id
                working_state.question_history.append(next_question.id)
                
            self._save_checkpoint(working_state)
            self.active_sessions[session_id] = working_state
            
            return working_state, next_question, record, decision

    def prepare_retry(self, session_id: str, question_id: str) -> Tuple[InterviewState, Question, Optional[AnswerRecord]]:
        """
        Prepares session to allow a retry on the specified question.
        Re-arms the current_question_id and records the previous answer for delta comparison.
        """
        with self._get_session_lock(session_id):
            state = self.get_session(session_id)
            if not state:
                raise ValueError(f"Invalid session ID: {session_id}")
            question = self.qb.get_question_by_id(question_id)
            if not question:
                raise ValueError(f"Question {question_id} not found.")

            orig_record = self.answer_records.get(f"{session_id}_{question_id}_latest")
            if orig_record:
                self.retry_originals[f"{session_id}_{question_id}"] = orig_record

            state.current_question_id = question_id
            if state.completion_status == "completed":
                state.completion_status = "in_progress"

            self._save_checkpoint(state)
            self.active_sessions[session_id] = state
            return state, question, orig_record

    def compare_answer_revision(self, original: AnswerRecord, revised: AnswerRecord) -> Dict[str, Any]:
        """
        Computes detailed score, dimensional, and qualitative deltas between original and revised answer.
        """
        orig_q = original.overall_answer_quality or 0.0
        rev_q = revised.overall_answer_quality or 0.0
        quality_delta = round((rev_q - orig_q) * 100, 1)

        dim_deltas = {}
        if original.structured_evaluation and revised.structured_evaluation:
            oe = original.structured_evaluation
            re = revised.structured_evaluation
            for dim in ["relevance", "clarity", "structure", "evidence_quality", "completeness", "technical_accuracy"]:
                ov = getattr(oe, dim, None)
                rv = getattr(re, dim, None)
                if ov is not None and rv is not None:
                    dim_deltas[dim] = round((rv - ov) * 100, 1)

        orig_strengths = set(s.lower() for s in original.detected_strengths)
        new_strengths = [s for s in revised.detected_strengths if s.lower() not in orig_strengths]

        rev_weaknesses = set(w.lower() for w in revised.detected_weaknesses)
        resolved_weaknesses = [w for w in original.detected_weaknesses if w.lower() not in rev_weaknesses]

        orig_wpm = original.speech_metrics.get("wpm") or 0.0
        rev_wpm = revised.speech_metrics.get("wpm") or 0.0
        wpm_delta = round(rev_wpm - orig_wpm, 1) if orig_wpm and rev_wpm else 0.0

        return {
            "original_answer_id": original.answer_id,
            "revised_answer_id": revised.answer_id,
            "overall_quality_delta_pts": quality_delta,
            "dimensional_deltas": dim_deltas,
            "new_strengths": new_strengths,
            "resolved_weaknesses": resolved_weaknesses,
            "wpm_delta": wpm_delta,
            "original_score": round(orig_q * 100),
            "revised_score": round(rev_q * 100),
            "is_improved": quality_delta > 0
        }

    def get_session(self, session_id: str) -> Optional[InterviewState]:
        if session_id in self.active_sessions:
            return self.active_sessions[session_id]
        
        # Try loading from disk
        path = os.path.join(self.checkpoint_dir, f"{session_id}.json")
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                state = InterviewState(**data)
                self.active_sessions[session_id] = state
                return state
        return None

    def _save_checkpoint(self, state: InterviewState):
        path = os.path.join(self.checkpoint_dir, f"{state.session_id}.json")
        with open(path, 'w', encoding='utf-8') as f:
            f.write(state.model_dump_json())
