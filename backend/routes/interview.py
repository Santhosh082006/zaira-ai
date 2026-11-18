from fastapi import APIRouter, HTTPException, File, UploadFile, Form, Response
from typing import Dict, Any
import os
import json
import tempfile
import asyncio
import hashlib
import traceback
import aiofiles

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
    RetryAnswerResponse,
    ResumeParseResponse
)
from core.interview_session import InterviewSessionService
from core.media_processor import MediaProcessor
from services.resume_parser import parse_resume_document

# TTS audio cache directory (disk-based, keyed by voice+text hash)
TTS_CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), '.cache', 'tts')
os.makedirs(TTS_CACHE_DIR, exist_ok=True)

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
            custom_goal=req.custom_goal,
            resume_text=req.resume_text,
            job_description=req.job_description
        )
        
        return StartInterviewResponse(
            session_id=state.session_id,
            current_question=_map_domain_question(first_question),
            interview_type=state.interview_type,
            interview_level=state.interview_level,
            assessment_goals=state.assessment_goals,
            technical_domain=state.technical_domain,
            custom_goal=state.custom_goal,
            resume_text=state.resume_text,
            job_description=state.job_description,
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
        from backend.routes.interview_ws import ws_manager
        from backend.schemas.interview_ws import WSServerProcessing, WSServerEvalStreamChunk

        def on_stage_cb(stage: str, message: str, progress: int):
            ws_manager.broadcast_sync(
                req.session_id,
                WSServerProcessing(stage=stage, progress=progress, message=message).model_dump_json()
            )

        def on_chunk_cb(chunk: str):
            ws_manager.broadcast_sync(
                req.session_id,
                WSServerEvalStreamChunk(stage="reasoning", chunk=chunk, progress=75).model_dump_json()
            )

        state, next_question, record, decision = session_service.process_candidate_answer(
            session_id=req.session_id,
            question_id=req.question_id,
            transcript=req.transcript,
            content_analysis=req.content_analysis,
            speech_metrics=req.speech_metrics,
            visual_metrics=req.visual_metrics,
            language_metrics=req.language_metrics,
            duration=req.duration,
            media_reference=req.media_reference,
            on_stage=on_stage_cb,
            on_chunk=on_chunk_cb
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

@router.get("/{session_id}/report")
def get_interview_report(session_id: str):
    """
    Cumulative final performance report card for an interview session.
    Aggregates multimodal telemetry, competency coverage, rubric breakdowns,
    and question-by-question performance audits.
    """
    state = session_service.get_session(session_id)
    if not state:
        raise HTTPException(status_code=404, detail=f"Interview session '{session_id}' not found.")

    # Collect all answer records
    records = []
    for ans_id in state.answer_history:
        rec = session_service.get_answer_record(ans_id)
        if rec:
            records.append(rec)

    # 1. Overall Score Calculation
    scores = [r.overall_answer_quality for r in records if r.overall_answer_quality is not None]
    if scores:
        overall_score = round((sum(scores) / len(scores)) * 100, 1)
    else:
        total_awarded = sum(r.total_marks_awarded for r in records)
        total_max = sum(r.total_max_marks for r in records)
        overall_score = round((total_awarded / total_max) * 100, 1) if total_max > 0 else 0.0

    # Qualitative Performance Rating
    if overall_score >= 85:
        performance_level = "Exemplary Delivery"
        summary_assessment = "Demonstrated commanding technical depth, clear structural articulation, and steady composure across all assessed dimensions."
    elif overall_score >= 70:
        performance_level = "Proficient Delivery"
        summary_assessment = "Demonstrated strong core competence with consistent articulation, accurate domain knowledge, and controlled delivery pacing."
    elif overall_score >= 55:
        performance_level = "Competent Delivery"
        summary_assessment = "Demonstrated baseline understanding with recognizable domain concepts; minor gaps observed in depth, structure, or precision."
    else:
        performance_level = "Developing Delivery"
        summary_assessment = "Demonstrated foundational awareness; recommended to strengthen direct structural flow, concrete evidence grounding, and domain accuracy."

    # 2. Competency Scores Breakdown
    competency_breakdown = []
    for comp_id, cov in state.competency_coverage.items():
        comp_obj = session_service.cm.get_competency_by_id(comp_id)
        name = comp_obj.name if comp_obj else comp_id
        category = comp_obj.category if comp_obj else "GENERAL"
        
        c_score = 0
        if cov.score is not None:
            c_score = round(cov.score * 100)
        elif cov.status == "demonstrated":
            c_score = 90
        elif cov.status == "partially_demonstrated":
            c_score = 65
        elif cov.status == "needs_improvement":
            c_score = 40
        else:
            c_score = 0

        findings = getattr(cov, "findings", []) or []
        competency_breakdown.append({
            "id": comp_id,
            "name": name,
            "category": category,
            "status": cov.status,
            "score": c_score,
            "evidence_count": len(cov.evidence_found),
            "evidence_found": cov.evidence_found,
            "findings": findings
        })

    # 3. Multimodal Telemetry Aggregate
    wpms = []
    face_ratios = []
    pause_secs = []
    total_duration = 0.0

    for r in records:
        total_duration += r.duration or 0.0
        sm = r.speech_metrics or {}
        w = sm.get("speaking_rate_wpm") or sm.get("wpm")
        if w and isinstance(w, (int, float)) and w > 0:
            wpms.append(float(w))
        p = sm.get("pause_duration_sec") or sm.get("total_pause_duration_sec")
        if p and isinstance(p, (int, float)):
            pause_secs.append(float(p))
        vm = r.visual_metrics or {}
        fr = vm.get("face_presence_ratio")
        if fr and isinstance(fr, (int, float)):
            face_ratios.append(float(fr))

    avg_wpm = round(sum(wpms) / len(wpms), 1) if wpms else None
    avg_face_presence = round((sum(face_ratios) / len(face_ratios)) * 100, 1) if face_ratios else None
    avg_pause = round(sum(pause_secs) / len(pause_secs), 1) if pause_secs else None

    aggregate_telemetry = {
        "avg_wpm": avg_wpm,
        "total_speaking_time_sec": round(total_duration, 1),
        "avg_face_presence_pct": avg_face_presence,
        "avg_pause_duration_sec": avg_pause,
        "total_questions_answered": len(records),
    }

    # 4. Question-by-Question Audit
    questions_audit = []
    for idx, r in enumerate(records):
        q = session_service.qb.get_question_by_id(r.question_id)
        q_text = q.question_text if q else f"Question {idx + 1}"
        q_type = q.question_type if q else "general"

        criteria_list = []
        for c in (r.rubric_criteria or []):
            criteria_list.append({
                "criterion_id": c.criterion_id,
                "criterion_name": c.criterion_name,
                "max_marks": c.max_marks,
                "marks_awarded": c.marks_awarded,
                "deduction": c.deduction,
                "status": c.status,
                "evidence_quote": c.evidence_quote,
                "reason_for_deduction": c.reason_for_deduction,
                "improvement_advice": c.improvement_advice,
                "exemplary_example": c.exemplary_example,
            })

        q_score = round((r.overall_answer_quality or 0.0) * 100) if r.overall_answer_quality is not None else 0
        wpm = (r.speech_metrics or {}).get("speaking_rate_wpm") or (r.speech_metrics or {}).get("wpm")

        actionable_list = []
        if r.actionable_findings:
            for af in r.actionable_findings:
                if hasattr(af, "model_dump"):
                    actionable_list.append(af.model_dump())
                elif isinstance(af, dict):
                    actionable_list.append(af)

        questions_audit.append({
            "question_number": idx + 1,
            "question_id": r.question_id,
            "question_text": q_text,
            "question_type": q_type,
            "transcript": r.transcript,
            "score": q_score,
            "total_marks_awarded": r.total_marks_awarded,
            "total_max_marks": r.total_max_marks,
            "duration_sec": round(r.duration, 1),
            "wpm": round(wpm, 1) if wpm else None,
            "rubric_criteria": criteria_list,
            "strengths": r.detected_strengths,
            "weaknesses": r.detected_weaknesses,
            "actionable_findings": actionable_list
        })

    # 5. Extract deduplicated session-wide strengths and growth targets
    all_strengths = list(dict.fromkeys(state.strengths + [s for r in records for s in r.detected_strengths]))
    all_weaknesses = list(dict.fromkeys(state.weaknesses + [w for r in records for w in r.detected_weaknesses]))

    return {
        "session_id": state.session_id,
        "interview_type": state.interview_type,
        "interview_level": state.interview_level,
        "technical_domain": state.technical_domain,
        "custom_goal": state.custom_goal,
        "overall_score": overall_score,
        "performance_level": performance_level,
        "summary_assessment": summary_assessment,
        "completion_status": state.completion_status,
        "aggregate_telemetry": aggregate_telemetry,
        "competency_breakdown": competency_breakdown,
        "strengths": all_strengths[:6],
        "growth_targets": all_weaknesses[:6],
        "questions_audit": questions_audit,
    }

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
        content_type = (file.content_type or "").lower()
        if content_type.startswith("audio/"):
            is_video = False
        elif content_type.startswith("video/"):
            is_video = True
        elif file.filename and "audio" in file.filename.lower():
            is_video = False
        elif suffix.lower() in [".mp4", ".mov", ".avi", ".mkv"]:
            is_video = True
        elif suffix.lower() in [".wav", ".mp3", ".ogg", ".m4a", ".aac", ".flac"]:
            is_video = False
        elif suffix.lower() == ".webm":
            is_video = "video" in content_type

        media_type = "video" if is_video else "audio"

        from backend.routes.interview_ws import ws_manager
        from backend.schemas.interview_ws import WSServerProcessing, WSServerEvalStreamChunk

        def on_stage_cb(stage: str, message: str, progress: int):
            ws_manager.broadcast_sync(
                session_id,
                WSServerProcessing(stage=stage, progress=progress, message=message).model_dump_json()
            )

        def on_chunk_cb(chunk: str):
            ws_manager.broadcast_sync(
                session_id,
                WSServerEvalStreamChunk(stage="reasoning", chunk=chunk, progress=75).model_dump_json()
            )

        # Invoke session service asynchronously to avoid blocking the event loop
        state, next_question, record, decision = await asyncio.to_thread(
            session_service.process_media_answer,
            session_id=session_id,
            question_id=question_id,
            media_path=tmp_path,
            media_type=media_type,
            media_processor=media_processor,
            on_stage=on_stage_cb,
            on_chunk=on_chunk_cb
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
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Internal Server Error during media evaluation: {str(e)}")
    finally:
        # Cleanup temp file safely
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass

@router.post("/parse-resume", response_model=ResumeParseResponse)
async def parse_resume_endpoint(file: UploadFile = File(...)):
    """
    Parses an uploaded resume file (PDF, DOCX, TXT) and returns cleanly extracted text and metadata.
    """
    try:
        content = await file.read()
        res = parse_resume_document(content, file.filename or "resume.pdf")
        return ResumeParseResponse(**res)
    except Exception as e:
        traceback.print_exc()
        return ResumeParseResponse(
            success=False,
            filename=file.filename or "uploaded_file",
            text="",
            word_count=0,
            char_count=0,
            page_count=0,
            error=f"Error parsing resume: {str(e)}"
        )

@router.post("/avatar/token", response_model=AvatarTokenResponse)
async def generate_avatar_session_token():
    """
    Secure server-to-server token generation for real-time HeyGen LiveAvatar Lite.
    Guarantees private API keys are never exposed to the frontend browser.
    Falls back gracefully if HEYGEN_API_KEY is not configured in .env.
    """
    api_key = os.getenv("HEYGEN_API_KEY", "").strip()
    avatar_id = os.getenv("HEYGEN_AVATAR_ID", "").strip()
    voice_id = os.getenv("HEYGEN_VOICE_ID", "").strip()

    if not api_key:
        return AvatarTokenResponse(
            available=False,
            provider="heygen_liveavatar",
            avatar_id=avatar_id or None,
            voice_id=voice_id or None,
            message="HEYGEN_API_KEY is not configured in .env. Please enter your credentials to activate LiveAvatar Lite."
        )

    import urllib.request
    import urllib.error
    import json

    loop = asyncio.get_event_loop()

    # 1. First attempt: LiveAvatar Lite API endpoint
    liveavatar_url = "https://api.liveavatar.com/v1/sessions/token"
    liveavatar_payload: Dict[str, Any] = {"mode": "LITE"}
    if avatar_id:
        liveavatar_payload["avatar_id"] = avatar_id
    if voice_id:
        liveavatar_payload["voice_id"] = voice_id

    req_live = urllib.request.Request(
        liveavatar_url,
        data=json.dumps(liveavatar_payload).encode("utf-8"),
        headers={
            "X-API-KEY": api_key,
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        },
        method="POST"
    )

    try:
        def _fetch_liveavatar():
            with urllib.request.urlopen(req_live, timeout=10) as resp:
                return json.loads(resp.read().decode("utf-8"))

        res_data = await loop.run_in_executor(None, _fetch_liveavatar)
        data = res_data.get("data", {}) if isinstance(res_data, dict) else {}
        token = data.get("session_token") or data.get("token") or res_data.get("token")
        session_id = data.get("session_id")
        
        if token:
            return AvatarTokenResponse(
                available=True,
                provider="heygen_liveavatar",
                token=token,
                session_id=session_id,
                avatar_id=avatar_id or data.get("avatar_id"),
                voice_id=voice_id or data.get("voice_id"),
                message="LiveAvatar Lite session token generated successfully."
            )
    except Exception as e_live:
        pass  # Fallback to streaming token endpoint below

    # 2. Second attempt: Classic HeyGen Streaming API endpoint
    streaming_url = "https://api.heygen.com/v1/streaming.create_token"
    streaming_req = urllib.request.Request(
        streaming_url,
        data=b"{}",
        headers={
            "x-api-key": api_key,
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        },
        method="POST"
    )

    try:
        def _fetch_streaming():
            with urllib.request.urlopen(streaming_req, timeout=10) as resp:
                return json.loads(resp.read().decode("utf-8"))

        res_data = await loop.run_in_executor(None, _fetch_streaming)
        token = res_data.get("data", {}).get("token") if isinstance(res_data, dict) else None
        
        if token:
            return AvatarTokenResponse(
                available=True,
                provider="heygen_liveavatar",
                token=token,
                avatar_id=avatar_id or "default",
                voice_id=voice_id or None,
                message="HeyGen Streaming session token generated successfully."
            )
        else:
            return AvatarTokenResponse(
                available=False,
                provider="heygen_liveavatar",
                avatar_id=avatar_id or None,
                voice_id=voice_id or None,
                message=f"HeyGen response did not contain an access token. Details: {res_data}"
            )
    except urllib.error.HTTPError as http_err:
        err_msg = http_err.read().decode("utf-8") if http_err.fp else str(http_err)
        return AvatarTokenResponse(
            available=False,
            provider="heygen_liveavatar",
            avatar_id=avatar_id or None,
            voice_id=voice_id or None,
            message=f"HeyGen authentication error ({http_err.code}): {err_msg}"
        )
    except Exception as e:
        return AvatarTokenResponse(
            available=False,
            provider="heygen_liveavatar",
            avatar_id=avatar_id or None,
            voice_id=voice_id or None,
            message=f"Unable to reach HeyGen API: {str(e)}"
        )

def format_conversational_speech_flow(text: str) -> str:
    """
    Transforms written interview prompts into natural, conversational spoken cadence:
    - Inserts subtle breath pauses before coordinating clauses ('... and ', '... specifically ').
    - Softens abrupt robotic punctuation and handles technical abbreviations.
    - Prevents rushing through long questions.
    """
    import re
    clean = text.strip()
    
    # Technical acronym smoothing for vocal clarity
    clean = re.sub(r'\bAPI\b', 'A-P-I', clean)
    clean = re.sub(r'\bAPIs\b', 'A-P-Is', clean)
    clean = re.sub(r'\bAWS\b', 'A-W-S', clean)
    clean = re.sub(r'\bGCP\b', 'G-C-P', clean)
    clean = re.sub(r'\bCI/CD\b', 'C-I C-D', clean)
    clean = re.sub(r'\bSQL\b', 'Sequel', clean, flags=re.IGNORECASE)
    clean = re.sub(r'\bNoSQL\b', 'No-Sequel', clean, flags=re.IGNORECASE)
    clean = re.sub(r'\bUI\b', 'U-I', clean)
    clean = re.sub(r'\bUX\b', 'U-X', clean)
    clean = re.sub(r'\bLLM\b', 'L-L-M', clean)
    clean = re.sub(r'\bLLMs\b', 'L-L-Ms', clean)
    clean = re.sub(r'\bDSA\b', 'D-S-A', clean)
    clean = re.sub(r'\bDBMS\b', 'D-B-M-S', clean)
    clean = re.sub(r'\bOOP\b', 'Object Oriented Programming', clean)
    clean = re.sub(r'\bOOPs\b', 'Object Oriented Programming', clean)
    clean = re.sub(r'\bHTML/CSS\b', 'H-T-M-L and C-S-S', clean)
    clean = re.sub(r'\bREST\b', 'Rest', clean)
    clean = re.sub(r'\bRESTful\b', 'Rest-ful', clean)

    # Conversational breath pauses before major joining phrases
    clean = re.sub(r',\s+(and|or|specifically|particularly|as well as|for instance|for example)\s+', r'... \1 ', clean, flags=re.IGNORECASE)
    clean = re.sub(r';\s*', '... ', clean)
    clean = re.sub(r':\s*', '... ', clean)
    
    # Natural cadence break for longer compound sentences
    if len(clean) > 60 and "... and " not in clean and ", and " not in clean:
        parts = re.split(r'(\s+and\s+)', clean, maxsplit=1)
        if len(parts) == 3 and len(parts[0]) > 25:
            clean = parts[0] + '... and ' + parts[2].strip()

    # Slight pause after introductory clauses
    clean = re.sub(r'^(To start with|First of all|For your first question|To begin|Let\'s begin|Moving on|Building on that)\s*,?\s*', r'\1... ', clean, flags=re.IGNORECASE)
    
    return clean

def _convert_to_pcm24k_chunks(mp3_bytes: bytes) -> Dict[str, Any]:
    """
    Converts MP3 audio to raw PCM 16-bit, 24,000 Hz, mono audio and partitions
    into LiveAvatar Lite WebSocket base64 chunks (400ms initial chunk, 1000ms subsequent).
    """
    import subprocess
    import imageio_ffmpeg
    import base64

    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    proc = subprocess.Popen(
        [
            ffmpeg_exe,
            "-v", "error",
            "-i", "pipe:0",
            "-f", "s16le",
            "-acodec", "pcm_s16le",
            "-ar", "24000",
            "-ac", "1",
            "pipe:1"
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    pcm_bytes, err = proc.communicate(input=mp3_bytes)
    if proc.returncode != 0 or not pcm_bytes:
        raise RuntimeError(f"FFmpeg PCM conversion failed: {err.decode('utf-8', errors='ignore')}")

    # LiveAvatar Lite chunk specification:
    # First chunk: 400ms = 24000 * 0.4 * 2 = 19200 bytes
    # Subsequent chunks: 1000ms = 24000 * 1.0 * 2 = 48000 bytes
    first_chunk_size = 19200
    subseq_chunk_size = 48000
    
    chunks = []
    total_len = len(pcm_bytes)
    if total_len <= first_chunk_size:
        chunks.append(base64.b64encode(pcm_bytes).decode("ascii"))
    else:
        chunks.append(base64.b64encode(pcm_bytes[:first_chunk_size]).decode("ascii"))
        for i in range(first_chunk_size, total_len, subseq_chunk_size):
            chunks.append(base64.b64encode(pcm_bytes[i:i + subseq_chunk_size]).decode("ascii"))
            
    duration = total_len / (24000 * 2)
    return {
        "status": "success",
        "format": "pcm_24k_16bit_mono",
        "sample_rate": 24000,
        "channels": 1,
        "duration_sec": round(duration, 3),
        "total_bytes": total_len,
        "chunks": chunks
    }

@router.post("/tts")
async def generate_speech_audio(req: TTSRequest):
    """
    Generate natural, conversational human-flow audio for talking avatar.
    Uses Microsoft Neural TTS with natural pacing, warm inflection, and conversational pauses.
    Supports MP3 binary stream and PCM 24kHz 16-bit mono base64 chunks for HeyGen LiveAvatar Lite.
    """
    if not req.text or not req.text.strip():
        raise HTTPException(status_code=422, detail="Text cannot be empty")
        
    try:
        import edge_tts
        voice = req.voice or "en-US-AvaNeural"
        rate = req.rate or "-3%"
        pitch = req.pitch or "+0Hz"
        is_pcm = (req.audio_format or "").lower() in ("pcm24k", "pcm")

        # Apply natural conversational speech formatting
        spoken_text = format_conversational_speech_flow(req.text) if req.conversational_flow else req.text.strip()

        # ── Cache lookup ────────────────────────────────────────────────
        cache_key = hashlib.sha256(f"{voice}:{rate}:{pitch}:{spoken_text}".encode()).hexdigest()
        cache_mp3_path = os.path.join(TTS_CACHE_DIR, f"{cache_key}.mp3")
        cache_pcm_path = os.path.join(TTS_CACHE_DIR, f"{cache_key}_pcm24k.json")

        loop = asyncio.get_event_loop()

        # Check PCM cache
        if is_pcm and os.path.exists(cache_pcm_path) and os.path.getsize(cache_pcm_path) > 0:
            try:
                async with aiofiles.open(cache_pcm_path, "r", encoding="utf-8") as f:
                    cached_json = await f.read()
                return json.loads(cached_json)
            except Exception:
                pass

        # Check MP3 cache
        audio_bytes = None
        if os.path.exists(cache_mp3_path) and os.path.getsize(cache_mp3_path) > 0:
            async with aiofiles.open(cache_mp3_path, "rb") as f:
                audio_bytes = await f.read()

        if not audio_bytes:
            # ── Synthesise via Edge-TTS with conversational prosody & retry ──────────
            audio_chunks = []
            for attempt in range(2):
                try:
                    communicate = edge_tts.Communicate(spoken_text, voice, rate=rate, pitch=pitch)
                    audio_chunks = []
                    async for chunk in communicate.stream():
                        if chunk["type"] == "audio":
                            audio_chunks.append(chunk["data"])
                    if audio_chunks:
                        break
                except Exception as tts_err:
                    if attempt == 1:
                        raise tts_err
                    await asyncio.sleep(0.5)
                    
            audio_bytes = b"".join(audio_chunks)
            if not audio_bytes:
                raise HTTPException(status_code=503, detail="TTS service returned empty audio stream.")

            # Write MP3 to cache
            async with aiofiles.open(cache_mp3_path, "wb") as f:
                await f.write(audio_bytes)

        if is_pcm:
            pcm_result = await loop.run_in_executor(None, _convert_to_pcm24k_chunks, audio_bytes)
            # Write PCM result to cache
            async with aiofiles.open(cache_pcm_path, "w") as f:
                await f.write(json.dumps(pcm_result))
            return pcm_result

        return Response(content=audio_bytes, media_type="audio/mpeg")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"TTS synthesis unavailable: {str(e)}")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"TTS synthesis unavailable: {str(e)}")
