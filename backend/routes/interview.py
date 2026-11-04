from fastapi import APIRouter, HTTPException, File, UploadFile, Form, Response
from typing import Dict, Any
import os
import tempfile
import asyncio

from backend.schemas.interview import (
    StartInterviewRequest,
    StartInterviewResponse,
    QuestionModel,
    AnswerSubmissionRequest,
    AnswerSubmissionResponse,
    NextQuestionDecisionModel,
    AvatarTokenResponse,
    TTSRequest,
    CompetencyEvidenceItem,
    StructuredEvaluationModel,
    ActionableFindingModel,
    RubricCriterionModel,
    RetryAnswerRequest,
    RetryAnswerResponse
)
from core.interview_session import InterviewSessionService
from core.media_processor import MediaProcessor

# Module-level singleton ensures sessions persist in memory across HTTP requests
session_service = InterviewSessionService()
media_processor = MediaProcessor()

router = APIRouter(prefix="/api/interview", tags=["Interview"])

def _map_domain_question(q) -> QuestionModel:
    if not q:
        return None
    return QuestionModel(
        id=q.id,
        question_text=q.question_text,
        question_type=q.question_type,
        difficulty=q.difficulty,
        topics=[q.topic] if q.topic and isinstance(q.topic, str) else q.topic if q.topic else []
    )

def _map_structured_evaluation(record, cm):
    if not record.structured_evaluation:
        return None
    se = record.structured_evaluation
    comp_items = []
    for ev in se.competency_evidence:
        comp_obj = cm.get_competency_by_id(ev.competency_id)
        comp_name = comp_obj.name if comp_obj else ev.competency_id
        comp_items.append(CompetencyEvidenceItem(
            competency_id=ev.competency_id,
            competency_name=comp_name,
            status=getattr(ev, "status", "not_assessed"),
            evidence_type=ev.evidence_type,
            excerpt=ev.excerpt,
            reasoning=ev.reasoning,
            score=getattr(ev, "score", None)
        ))

    finding_items = []
    for f in getattr(se, "actionable_findings", []):
        finding_items.append(ActionableFindingModel(
            finding=f.finding,
            supporting_evidence=f.supporting_evidence,
            explanation=f.explanation,
            specific_correction=f.specific_correction,
            example_or_model_answer=f.example_or_model_answer
        ))

    rubric_items = []
    for rc in getattr(se, "rubric_criteria", []):
        rubric_items.append(RubricCriterionModel(
            criterion_id=rc.criterion_id,
            criterion_name=rc.criterion_name,
            max_marks=rc.max_marks,
            marks_awarded=rc.marks_awarded,
            deduction=getattr(rc, "deduction", 0.0),
            status=getattr(rc, "status", "evaluated"),
            evidence_quote=getattr(rc, "evidence_quote", None),
            reason_for_deduction=getattr(rc, "reason_for_deduction", None),
            improvement_advice=getattr(rc, "improvement_advice", None),
            exemplary_example=getattr(rc, "exemplary_example", None)
        ))

    return StructuredEvaluationModel(
        evaluation_status=se.evaluation_status,
        overall_quality=se.overall_quality,
        relevance=se.relevance,
        clarity=se.clarity,
        structure=se.structure,
        evidence_quality=se.evidence_quality,
        completeness=se.completeness,
        technical_accuracy=se.technical_accuracy,
        strengths=se.strengths,
        areas_to_improve=se.areas_to_improve,
        recommendations=getattr(se, "recommendations", []),
        evidence_excerpts=se.evidence_excerpts,
        competency_evidence=comp_items,
        actionable_findings=finding_items,
        rubric_criteria=rubric_items,
        total_max_marks=getattr(se, "total_max_marks", 10.0),
        total_marks_awarded=getattr(se, "total_marks_awarded", 0.0),
        is_transcription_error=getattr(se, "is_transcription_error", False),
        transcription_error_details=getattr(se, "transcription_error_details", None),
        evaluation_limitations=se.evaluation_limitations,
        is_garbled_transcript=getattr(se, "is_garbled_transcript", False),
        garbled_reason=getattr(se, "garbled_reason", None)
    )

@router.post("/start", response_model=StartInterviewResponse)
def start_interview(req: StartInterviewRequest):
    try:
        state, first_question = session_service.start_interview(
            interview_type=req.interview_type,
            interview_level=req.interview_level,
            assessment_goals=req.assessment_goals,
            technical_domain=req.technical_domain,
            custom_goal=req.custom_goal
        )
        
        return StartInterviewResponse(
            session_id=state.session_id,
            current_question=_map_domain_question(first_question),
            interview_type=state.interview_type,
            interview_level=state.interview_level,
            assessment_goals=state.assessment_goals,
            technical_domain=state.technical_domain,
            custom_goal=state.custom_goal,
            completion_status=state.completion_status,
            interview_progress=state.interview_progress
        )
    except Exception as e:
        # Avoid exposing raw Python stack traces
        raise HTTPException(status_code=500, detail="Internal Server Error during initialization")

def _map_actionable_findings(record):
    findings = []
    source = getattr(record, "actionable_findings", [])
    if not source and record.structured_evaluation:
        source = getattr(record.structured_evaluation, "actionable_findings", [])
    for f in source:
        findings.append(ActionableFindingModel(
            finding=f.finding,
            supporting_evidence=f.supporting_evidence,
            explanation=f.explanation,
            specific_correction=f.specific_correction,
            example_or_model_answer=f.example_or_model_answer
        ))
    return findings

@router.post("/answer", response_model=AnswerSubmissionResponse)
def submit_answer(req: AnswerSubmissionRequest):
    try:
        state, next_question, record, decision = session_service.process_candidate_answer(
            session_id=req.session_id,
            question_id=req.question_id,
            transcript=req.transcript,
            content_analysis=req.content_analysis,
            speech_metrics=req.speech_metrics,
            visual_metrics=req.visual_metrics,
            language_metrics=req.language_metrics,
            duration=req.duration,
            media_reference=req.media_reference
        )
        
        coverage_status = {k: v.status for k, v in state.competency_coverage.items()}
        
        mapped_se = _map_structured_evaluation(record, session_service.cm)
        return AnswerSubmissionResponse(
            session_id=state.session_id,
            answer_id=record.answer_id,
            processed_question_id=req.question_id,
            next_question=_map_domain_question(next_question),
            decision=NextQuestionDecisionModel(
                decision_type=decision.decision_type,
                reason=decision.reason,
                next_question_id=decision.next_question_id
            ),
            interview_progress=state.interview_progress,
            completion_status=state.completion_status,
            competency_coverage_status=coverage_status,
            language_metrics=record.language_metrics,
            speech_metrics=getattr(record, "speech_metrics", None),
            visual_metrics=getattr(record, "visual_metrics", None),
            transcript=record.transcript,
            overall_answer_quality=record.overall_answer_quality,
            detected_strengths=record.detected_strengths,
            detected_weaknesses=record.detected_weaknesses,
            detected_topics=record.detected_topics,
            recommendations=getattr(record, "recommendations", []) or (record.structured_evaluation.recommendations if record.structured_evaluation else []),
            structured_evaluation=mapped_se,
            actionable_findings=_map_actionable_findings(record),
            rubric_criteria=mapped_se.rubric_criteria if mapped_se else [],
            total_max_marks=mapped_se.total_max_marks if mapped_se else 10.0,
            total_marks_awarded=mapped_se.total_marks_awarded if mapped_se else 0.0,
            is_transcription_error=mapped_se.is_transcription_error if mapped_se else False,
            transcription_error_details=mapped_se.transcription_error_details if mapped_se else None,
            is_revision=getattr(record, "is_revision", False),
            revision_delta=session_service.revision_deltas.get(record.answer_id)
        )
    except ValueError as ve:
        err = str(ve)
        if "Invalid session ID" in err:
            raise HTTPException(status_code=404, detail="Session not found")
        elif "Wrong question ID" in err or "already completed" in err:
            raise HTTPException(status_code=409, detail=err)
        else:
            raise HTTPException(status_code=422, detail=err)
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal Server Error during evaluation")

@router.post("/retry", response_model=RetryAnswerResponse)
def retry_answer(req: RetryAnswerRequest):
    try:
        state, question, orig_record = session_service.prepare_retry(
            session_id=req.session_id,
            question_id=req.question_id
        )
        return RetryAnswerResponse(
            session_id=state.session_id,
            question=_map_domain_question(question),
            previous_answer_id=orig_record.answer_id if orig_record else None,
            previous_score=orig_record.overall_answer_quality if orig_record else None,
            message=f"Session re-armed for retry of question {req.question_id}."
        )
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal Server Error preparing retry")

@router.get("/state/{session_id}")
def get_interview_state(session_id: str):
    state = session_service.get_session(session_id)
    if not state:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Safely dump Pydantic model
    return state.model_dump()

@router.post("/{session_id}/answer/media", response_model=AnswerSubmissionResponse)
async def submit_media_answer(
    session_id: str,
    question_id: str = Form(...),
    file: UploadFile = File(...)
):
    # Save uploaded file to temp path
    suffix = os.path.splitext(file.filename)[1] if file.filename else ".webm"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        # Determine whether file is video or audio-only
        is_video = False
        if file.content_type and file.content_type.startswith("video/"):
            is_video = True
        elif suffix.lower() in [".webm", ".mp4", ".mov", ".avi", ".mkv"]:
            is_video = True

        media_type = "video" if is_video else "audio"

        # Invoke session service asynchronously to avoid blocking the event loop
        state, next_question, record, decision = await asyncio.to_thread(
            session_service.process_media_answer,
            session_id=session_id,
            question_id=question_id,
            media_path=tmp_path,
            media_type=media_type,
            media_processor=media_processor
        )

        coverage_status = {k: v.status for k, v in state.competency_coverage.items()}
        
        mapped_se = _map_structured_evaluation(record, session_service.cm)
        return AnswerSubmissionResponse(
            session_id=state.session_id,
            answer_id=record.answer_id,
            processed_question_id=question_id,
            next_question=_map_domain_question(next_question),
            decision=NextQuestionDecisionModel(
                decision_type=decision.decision_type,
                reason=decision.reason,
                next_question_id=decision.next_question_id
            ),
            interview_progress=state.interview_progress,
            completion_status=state.completion_status,
            competency_coverage_status=coverage_status,
            language_metrics=record.language_metrics,
            speech_metrics=getattr(record, "speech_metrics", None),
            visual_metrics=getattr(record, "visual_metrics", None),
            transcript=record.transcript,
            overall_answer_quality=record.overall_answer_quality,
            detected_strengths=record.detected_strengths,
            detected_weaknesses=record.detected_weaknesses,
            detected_topics=record.detected_topics,
            recommendations=getattr(record, "recommendations", []) or (record.structured_evaluation.recommendations if record.structured_evaluation else []),
            structured_evaluation=mapped_se,
            actionable_findings=_map_actionable_findings(record),
            rubric_criteria=mapped_se.rubric_criteria if mapped_se else [],
            total_max_marks=mapped_se.total_max_marks if mapped_se else 10.0,
            total_marks_awarded=mapped_se.total_marks_awarded if mapped_se else 0.0,
            is_transcription_error=mapped_se.is_transcription_error if mapped_se else False,
            transcription_error_details=mapped_se.transcription_error_details if mapped_se else None,
            is_revision=getattr(record, "is_revision", False),
            revision_delta=session_service.revision_deltas.get(record.answer_id)
        )
    except ValueError as ve:
        err = str(ve)
        if "Invalid session ID" in err:
            raise HTTPException(status_code=404, detail="Session not found")
        elif "Wrong question ID" in err or "already completed" in err:
            raise HTTPException(status_code=409, detail=err)
        else:
            raise HTTPException(status_code=422, detail=err)
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal Server Error during media evaluation")
    finally:
        # Cleanup temp file safely
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass

@router.post("/avatar/token", response_model=AvatarTokenResponse)
async def generate_avatar_session_token():
    """
    Secure server-to-server token generation for real-time streaming avatars.
    Guarantees private API keys are never exposed to the frontend browser.
    Falls back gracefully if HEYGEN_API_KEY is not configured.
    """
    api_key = os.getenv("HEYGEN_API_KEY")
    if not api_key:
        return AvatarTokenResponse(
            available=False,
            provider="heygen",
            message="HEYGEN_API_KEY is not configured in the environment."
        )
    
    import urllib.request
    import json
    
    url = "https://api.heygen.com/v1/streaming.create_token"
    req = urllib.request.Request(
        url,
        data=b"{}",
        headers={
            "x-api-key": api_key,
            "Content-Type": "application/json"
        },
        method="POST"
    )
    
    try:
        loop = asyncio.get_event_loop()
        def _fetch():
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read().decode("utf-8"))
        res_data = await loop.run_in_executor(None, _fetch)
        token = res_data.get("data", {}).get("token")
        if token:
            return AvatarTokenResponse(
                available=True,
                provider="heygen",
                token=token
            )
        else:
            return AvatarTokenResponse(
                available=False,
                provider="heygen",
                message="HeyGen response did not contain an access token."
            )
    except Exception as e:
        return AvatarTokenResponse(
            available=False,
            provider="heygen",
            message=f"HeyGen token request failed: {str(e)}"
        )

@router.post("/tts")
async def generate_speech_audio(req: TTSRequest):
    """
    Generate audio for open-source client-side talking avatar lip-sync.
    100% free, zero external API keys, zero paid subscriptions.
    Returns audio/mpeg stream directly to the browser for TalkingAvatar.speak(blob).
    """
    if not req.text or not req.text.strip():
        raise HTTPException(status_code=422, detail="Text cannot be empty")
        
    try:
        import edge_tts
        voice = req.voice or "en-US-AvaNeural"
        communicate = edge_tts.Communicate(req.text.strip(), voice)
        
        audio_chunks = []
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_chunks.append(chunk["data"])
                
        audio_bytes = b"".join(audio_chunks)
        if not audio_bytes:
            raise HTTPException(status_code=503, detail="TTS service returned empty audio stream.")
            
        return Response(content=audio_bytes, media_type="audio/mpeg")
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"TTS synthesis unavailable: {str(e)}")
