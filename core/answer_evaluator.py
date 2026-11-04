import uuid
from typing import Tuple, Dict, Any, List, Optional

from core.schemas import InterviewState, Question, AnswerRecord
from core.competency_map import CompetencyMap
from services.answer_evaluator_llm import verify_and_align_evidence_quote

class AnswerEvaluator:
    """
    Integration layer that converts outputs from TruthLens analysis engines
    into structured AnswerRecords and updates the InterviewState.
    """
    def __init__(self, competency_map: CompetencyMap):
        self.cm = competency_map

    def process_answer(
        self,
        state: InterviewState,
        question: Question,
        transcript: str,
        content_analysis: Dict[str, Any],
        speech_metrics: Optional[Dict[str, float]] = None,
        visual_metrics: Optional[Dict[str, float]] = None,
        language_metrics: Optional[Dict[str, float]] = None,
        duration: float = 0.0,
        media_reference: str = ""
    ) -> Tuple[InterviewState, AnswerRecord]:
        
        speech_metrics = speech_metrics or {}
        visual_metrics = visual_metrics or {}
        language_metrics = language_metrics or {}
        
        answer_id = f"ans_{uuid.uuid4().hex[:8]}"
        
        # Determine target competencies
        target_comps = []
        for cid in question.competencies:
            comp = self.cm.get_competency_by_id(cid)
            if comp: target_comps.append(comp)
            
        # 1. Run Structured Evaluation if LLM enabled
        from services.answer_evaluator_llm import generate_structured_evaluation
        
        evaluation = None
        # Only run LLM evaluation if content_analysis is empty (legacy fallback) and there's a transcript
        if not content_analysis and transcript and transcript.strip():
            evaluation = generate_structured_evaluation(
                question=question,
                transcript=transcript,
                interview_type=state.interview_type,
                level=state.interview_level,
                assessment_goals=state.assessment_goals,
                target_competencies=target_comps
            )
            
        # 2. Calculate Bounded Overall Quality
        overall_quality = None
        if evaluation:
            if evaluation.evaluation_status == "success" and evaluation.overall_quality is not None:
                overall_quality = evaluation.overall_quality
        else:
            overall_quality = self._calculate_overall_quality(content_analysis)
        
        # 3. Extract structured content details
        strengths = []
        weaknesses = []
        recommendations = []
        
        if evaluation:
            if evaluation.evaluation_status == "success":
                strengths.extend(evaluation.strengths)
                weaknesses.extend(evaluation.areas_to_improve)
                recommendations.extend(getattr(evaluation, "recommendations", []))
        else:
            # Legacy fallback
            for category, data in content_analysis.items():
                if not isinstance(data, dict):
                    continue
                if str(data.get("score", "")) == "Insufficient Data":
                    continue
                    
                www = data.get("what_went_well")
                if www and www != "N/A":
                    strengths.append(www)
                    
                wni = data.get("what_needs_improvement")
                if wni and wni != "N/A":
                    weaknesses.append(wni)
                
        # Handle facts if the story analyzer provided them
        facts = content_analysis.get("story_facts", {})
        detected_topics = facts.get("topics", [])
        detected_claims = facts.get("claims", [])
                
        # 4. Map Evidence to Target Competencies
        competency_evidence = {}
        comp_status_map = {}
        comp_score_map = {}

        if evaluation:
            if evaluation.evaluation_status == "success":
                for ev in evaluation.competency_evidence:
                    cid = ev.competency_id
                    
                    # Validate ID
                    if cid not in question.competencies or not self.cm.get_competency_by_id(cid):
                        continue
                    
                    # Transcript validation for direct quotes
                    if ev.excerpt and ev.excerpt.strip():
                        verified_excerpt = verify_and_align_evidence_quote(ev.excerpt, transcript)
                        if verified_excerpt:
                            ev.excerpt = verified_excerpt
                        else:
                            evaluation.evaluation_limitations.append(
                                f"Discarded misquoted excerpt for {cid}."
                            )
                            ev.excerpt = None
                            
                    status_label = ev.status.upper().replace("_", " ") if hasattr(ev, "status") and ev.status else "EVIDENCE"
                    if cid not in competency_evidence:
                        competency_evidence[cid] = []
                    competency_evidence[cid].append(f"[{status_label}] {ev.reasoning}")
                    if hasattr(ev, "status") and ev.status:
                        comp_status_map[cid] = ev.status
                    if hasattr(ev, "score") and ev.score is not None:
                        comp_score_map[cid] = ev.score
        else:
            competency_evidence = self._extract_evidence(question.competencies, content_analysis)
        
        # 5. Construct Answer Record
        actionable_findings = getattr(evaluation, "actionable_findings", []) if evaluation else []
        rubric_criteria = getattr(evaluation, "rubric_criteria", []) if evaluation else []
        total_max_marks = getattr(evaluation, "total_max_marks", 10.0) if evaluation else 10.0
        total_marks_awarded = getattr(evaluation, "total_marks_awarded", 0.0) if evaluation else 0.0
        record = AnswerRecord(
            answer_id=answer_id,
            session_id=state.session_id,
            question_id=question.id,
            media_reference=media_reference,
            transcript=transcript,
            duration=duration,
            speech_metrics=speech_metrics,
            visual_metrics=visual_metrics,
            language_metrics=language_metrics,
            content_analysis=content_analysis,
            structured_evaluation=evaluation,
            rubric_criteria=rubric_criteria,
            total_max_marks=total_max_marks,
            total_marks_awarded=total_marks_awarded,
            actionable_findings=actionable_findings,
            detected_strengths=strengths,
            detected_weaknesses=weaknesses,
            recommendations=recommendations,
            detected_topics=detected_topics,
            detected_claims=detected_claims,
            competency_evidence=competency_evidence,
            overall_answer_quality=overall_quality
        )
        
        # 6. Update State
        state.answer_history.append(answer_id)
        state.strengths.extend(strengths)
        state.weaknesses.extend(weaknesses)
        
        if detected_topics:
            state.topics_discussed.extend(detected_topics)
        if detected_claims:
            state.claims_detected.extend(detected_claims)
            
        # Deduplicate state arrays
        state.strengths = list(set(state.strengths))
        state.weaknesses = list(set(state.weaknesses))
        state.topics_discussed = list(set(state.topics_discussed))
        state.claims_detected = list(set(state.claims_detected))
        
        # Update Competency Coverage with explicit rubrics & scores
        for comp_id in question.competencies:
            if comp_id not in state.competencies_tested:
                state.competencies_tested.append(comp_id)
            
            cov = state.competency_coverage.get(comp_id)
            if cov:
                new_evidence = competency_evidence.get(comp_id, [])
                explicit_status = comp_status_map.get(comp_id)
                explicit_score = comp_score_map.get(comp_id)
                self.cm.evaluate_coverage(
                    cov,
                    new_evidence,
                    explicit_status=explicit_status,
                    explicit_score=explicit_score
                )
                
        # Maintain convenience state (competencies_missing)
        state.competencies_missing = [
            cid for cid in state.competencies_missing 
            if state.competency_coverage.get(cid) and state.competency_coverage[cid].status != "demonstrated"
        ]

        return state, record

    def _calculate_overall_quality(self, content_analysis: Dict[str, Any]) -> Optional[float]:
        """
        Derives a simple bounded 0.0-1.0 quality score from available analysis modules.
        Will reuse the existing 0-100 scores from the TruthLens evaluator if available.
        """
        scores = []
        for cat, data in content_analysis.items():
            if isinstance(data, dict):
                val = data.get("score")
                if isinstance(val, (int, float)):
                    scores.append(val)
        
        if scores:
            # Convert 0-100 to 0.0-1.0
            return sum(scores) / len(scores) / 100.0
            
        return None # Missing data does not mean average quality.

    def _extract_evidence(self, target_competencies: List[str], content_analysis: Dict[str, Any]) -> Dict[str, List[str]]:
        """
        Maps existing analytical observations to target competencies safely.
        Uses deterministic keyword matching against competency definitions to prevent hallucination.
        """
        evidence_map = {cid: [] for cid in target_competencies}
        
        # Pool all valid observations from the analysis
        all_obs = []
        for cat, data in content_analysis.items():
            if not isinstance(data, dict):
                continue
            if str(data.get("score", "")) == "Insufficient Data":
                continue
                
            obs = data.get("evidence_observation")
            if obs and obs != "N/A":
                all_obs.append(obs)
                
            # Treat strengths as valid evidence
            www = data.get("what_went_well")
            if www and www != "N/A":
                all_obs.append(www)
                
        # Deterministic attribution
        for comp_id in target_competencies:
            comp = self.cm.get_competency_by_id(comp_id)
            if not comp:
                continue
                
            # Build a keyword signature for this competency
            keywords = set(comp.name.lower().split())
            for marker in comp.evidence_markers:
                # Include significant words from evidence markers
                keywords.update([w for w in marker.lower().split() if len(w) > 3])
                
            for obs in all_obs:
                obs_lower = obs.lower()
                # If observation shares meaningful vocabulary with the competency, attribute it.
                if any(kw in obs_lower for kw in keywords):
                    if obs not in evidence_map[comp_id]:
                        evidence_map[comp_id].append(obs)
            
        return evidence_map
