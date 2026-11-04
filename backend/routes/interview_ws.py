import json
import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from backend.routes.interview import session_service, _map_domain_question
from backend.schemas.interview_ws import (
    WSClientSubmitAnswer,
    WSClientGetState,
    WSClientLiveTranscriptUpdate,
    WSServerConnected,
    WSServerQuestionReady,
    WSServerProcessing,
    WSServerAnswerResult,
    WSServerInterviewCompleted,
    WSServerError,
    WSServerState,
    WSServerLiveFeedback
)
from services.live_feedback_analyzer import analyze_live_transcript
import time

ws_router = APIRouter(tags=["Interview WebSocket"])

@ws_router.websocket("/ws/interview/{session_id}")
async def interview_websocket(websocket: WebSocket, session_id: str):
    # 1. Accept connection
    await websocket.accept()

    # 2. Validate session
    state = session_service.get_session(session_id)
    if not state:
        await websocket.send_text(WSServerError(
            code="INVALID_SESSION",
            message="Interview session not found."
        ).model_dump_json())
        await websocket.close(code=1008)
        return

    # 3. Send connected event
    await websocket.send_text(WSServerConnected(session_id=session_id).model_dump_json())

    # 4. Provide current state / question
    if state.completion_status == "completed":
        await websocket.send_text(WSServerInterviewCompleted(
            reason="Session was already completed upon connection."
        ).model_dump_json())
    else:
        if state.current_question_id:
            # Look up question safely
            q_domain = session_service.qb.get_question_by_id(state.current_question_id)
            if q_domain:
                q_model = _map_domain_question(q_domain)
                await websocket.send_text(WSServerQuestionReady(question=q_model.model_dump()).model_dump_json())

    # 5. Receive messages
    last_feedback_time = 0.0
    try:
        while True:
            data_str = await websocket.receive_text()
            try:
                msg_dict = json.loads(data_str)
            except json.JSONDecodeError:
                await websocket.send_text(WSServerError(
                    code="MALFORMED_MESSAGE",
                    message="Invalid JSON format."
                ).model_dump_json())
                continue

            msg_type = msg_dict.get("type")

            if msg_type == "live_transcript_update":
                try:
                    update_req = WSClientLiveTranscriptUpdate(**msg_dict)
                except ValidationError:
                    await websocket.send_text(WSServerError(
                        code="MALFORMED_MESSAGE",
                        message="Invalid live_transcript_update payload"
                    ).model_dump_json())
                    continue

                current_state = session_service.get_session(session_id)
                if not current_state or current_state.completion_status == "completed":
                    continue

                # Throttle live feedback calculation to at most once per 1.5 seconds unless marked final
                now = time.time()
                if not update_req.is_final and (now - last_feedback_time) < 1.5:
                    continue

                q_obj = session_service.qb.get_question_by_id(update_req.question_id)
                if not q_obj:
                    continue

                last_feedback_time = now
                feedback_result = analyze_live_transcript(
                    question=q_obj,
                    transcript=update_req.transcript,
                    speaking_duration_sec=update_req.duration
                )

                await websocket.send_text(WSServerLiveFeedback(
                    question_id=update_req.question_id,
                    word_count=feedback_result["word_count"],
                    concepts_covered=feedback_result["concepts_covered"],
                    concepts_missing=feedback_result["concepts_missing"],
                    pacing_status=feedback_result["pacing_status"],
                    coaching_hint=feedback_result["coaching_hint"],
                    is_provisional=True
                ).model_dump_json())

            elif msg_type == "get_state":
                try:
                    _ = WSClientGetState(**msg_dict)
                except ValidationError:
                    await websocket.send_text(WSServerError(code="MALFORMED_MESSAGE", message="Invalid get_state payload").model_dump_json())
                    continue
                
                current_state = session_service.get_session(session_id)
                if not current_state:
                    await websocket.send_text(WSServerError(code="INVALID_SESSION", message="Session missing").model_dump_json())
                    continue
                
                coverage_status = {k: v.status for k, v in current_state.competency_coverage.items()}
                
                await websocket.send_text(WSServerState(
                    session_id=session_id,
                    completion_status=current_state.completion_status,
                    current_question_id=current_state.current_question_id,
                    interview_progress=current_state.interview_progress,
                    competency_coverage_status=coverage_status
                ).model_dump_json())

            elif msg_type == "submit_answer":
                try:
                    ans_req = WSClientSubmitAnswer(**msg_dict)
                except ValidationError as e:
                    await websocket.send_text(WSServerError(
                        code="MALFORMED_MESSAGE",
                        message="Invalid submit_answer payload."
                    ).model_dump_json())
                    continue
                
                current_state = session_service.get_session(session_id)
                if not current_state:
                    await websocket.send_text(WSServerError(code="INVALID_SESSION", message="Session missing").model_dump_json())
                    continue
                    
                if current_state.completion_status == "completed":
                    await websocket.send_text(WSServerError(code="COMPLETED_INTERVIEW", message="Interview is already completed").model_dump_json())
                    continue
                    
                if current_state.current_question_id != ans_req.question_id:
                    await websocket.send_text(WSServerError(code="WRONG_QUESTION", message="Wrong question ID submitted").model_dump_json())
                    continue
                
                # Emit processing events deterministically
                await websocket.send_text(WSServerProcessing(stage="received", progress=10).model_dump_json())
                await asyncio.sleep(0.1) # Simulate async processing
                await websocket.send_text(WSServerProcessing(stage="evaluating", progress=50).model_dump_json())
                await asyncio.sleep(0.1)
                
                try:
                    # Invoke domain service (synchronous call - explicitly off the async event loop)
                    upd_state, next_q, record, decision = await asyncio.to_thread(
                        session_service.process_candidate_answer,
                        session_id=session_id,
                        question_id=ans_req.question_id,
                        transcript=ans_req.transcript,
                        content_analysis=ans_req.content_analysis or {},
                        speech_metrics=ans_req.speech_metrics,
                        visual_metrics=ans_req.visual_metrics,
                        language_metrics=ans_req.language_metrics,
                        duration=ans_req.duration,
                        media_reference=ans_req.media_reference or ""
                    )
                    
                    await websocket.send_text(WSServerProcessing(stage="selecting_next_question", progress=90).model_dump_json())
                    
                    if upd_state.completion_status == "completed":
                        await websocket.send_text(WSServerInterviewCompleted(reason=decision.decision_type).model_dump_json())
                    else:
                        nq_model_dict = _map_domain_question(next_q).model_dump() if next_q else None
                        await websocket.send_text(WSServerAnswerResult(
                            answer_id=record.answer_id,
                            question_id=ans_req.question_id,
                            next_question=nq_model_dict,
                            decision=decision.decision_type,
                            decision_reason=decision.reason,
                            interview_progress=upd_state.interview_progress,
                            completion_status=upd_state.completion_status
                        ).model_dump_json())
                        
                except ValueError as ve:
                    # Duplicate answer or wrong question that sneaked past early checks
                    await websocket.send_text(WSServerError(code="WRONG_QUESTION", message=str(ve)).model_dump_json())
                except Exception as e:
                    await websocket.send_text(WSServerError(code="INTERNAL_ERROR", message="Unexpected internal error").model_dump_json())
            else:
                await websocket.send_text(WSServerError(
                    code="UNKNOWN_MESSAGE_TYPE",
                    message=f"Unknown message type: {msg_type}"
                ).model_dump_json())

    except WebSocketDisconnect:
        # Gracefully handle disconnect. Do not alter InterviewState.
        pass
    except Exception as e:
        # Failsafe catch-all to prevent server crash and avoid leaking stack traces
        try:
            await websocket.send_text(WSServerError(
                code="INTERNAL_ERROR",
                message="Unexpected connection error."
            ).model_dump_json())
            await websocket.close(code=1011)
        except:
            pass
