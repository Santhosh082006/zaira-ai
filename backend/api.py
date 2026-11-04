import asyncio
import json
import os
import shutil
import uuid
from typing import Optional, Dict, Any
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File, Form, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import sys

# Ensure the root project directory is in the path for module imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.constants import VIDEO_DIR, AUDIO_DIR, INSUFFICIENT_DATA
from processors.ingestion.video_demuxer import demux_video_to_audio
from services.speech_to_text import transcribe_audio, load_whisper_model
from services.speech_features import extract_speech_features
from services.visual_features import extract_visual_features
from services.story_analyzer import extract_story_facts
from analytical_engine.evaluator import (
    compute_deterministic_scores,
    calculate_overall_communication_score,
)

from backend.routes.interview import router as interview_router
from backend.routes.interview_ws import ws_router as interview_ws_router

app = FastAPI(title="TruthLens AI 2.0 Real API")

app.include_router(interview_router)
app.include_router(interview_ws_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, session_id: str):
        await websocket.accept()
        self.active_connections[session_id] = websocket

    def disconnect(self, session_id: str):
        if session_id in self.active_connections:
            del self.active_connections[session_id]

    async def send_status(self, session_id: str, message: str, progress: int):
        if session_id in self.active_connections:
            await self.active_connections[session_id].send_json({
                "status": message,
                "progress": progress
            })

manager = ConnectionManager()

# Session storage for video analysis results
CHECKPOINT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".sessions")
os.makedirs(CHECKPOINT_DIR, exist_ok=True)
analysis_sessions: Dict[str, Dict[str, Any]] = {}

def _save_session_checkpoint(session_id: str, data: dict):
    try:
        path = os.path.join(CHECKPOINT_DIR, f"analysis_{session_id}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)
    except Exception as e:
        print(f"Warning: Failed to save checkpoint for analysis session {session_id}: {e}")

def _load_session_checkpoint(session_id: str) -> Optional[dict]:
    path = os.path.join(CHECKPOINT_DIR, f"analysis_{session_id}.json")
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Warning: Failed to load checkpoint for analysis session {session_id}: {e}")
            return None
    return None

@app.get("/api/health")
async def health_check():
    return {"status": "FastAPI Real Pipeline is running."}

@app.websocket("/api/ws/status/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    await manager.connect(websocket, session_id)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(session_id)

async def run_real_pipeline(session_id: str, video_path: str):
    try:
        analysis_sessions[session_id] = {
            "session_id": session_id,
            "status": "processing",
            "progress": 5,
            "message": "Initializing analysis pipeline...",
        }
        _save_session_checkpoint(session_id, analysis_sessions[session_id])

        # Step 1: Demux
        await manager.send_status(session_id, "Extracting audio track...", 10)
        analysis_sessions[session_id]["progress"] = 10
        analysis_sessions[session_id]["message"] = "Extracting audio track..."
        audio_path = os.path.join(AUDIO_DIR, f"session_{session_id}_extracted.wav")
        success, err = await asyncio.to_thread(demux_video_to_audio, video_path, audio_path)
        
        if not success:
            raise RuntimeError(f"Audio demux failed: {err}")

        # Step 2: Transcribe
        await manager.send_status(session_id, "Transcribing speech...", 30)
        analysis_sessions[session_id]["progress"] = 30
        analysis_sessions[session_id]["message"] = "Transcribing speech..."
        try:
            model = await asyncio.to_thread(load_whisper_model)
            transcript = await asyncio.to_thread(transcribe_audio, model, audio_path)
        except Exception as e:
            print(f"Whisper transcription failed or unavailable: {e}")
            transcript = ""

        # Step 3: Speech Features
        await manager.send_status(session_id, "Analyzing vocal delivery...", 50)
        analysis_sessions[session_id]["progress"] = 50
        analysis_sessions[session_id]["message"] = "Analyzing vocal delivery..."
        try:
            speech_feats = await asyncio.to_thread(extract_speech_features, audio_path, transcript)
        except Exception as e:
            print(f"Speech feature extraction failed: {e}")
            speech_feats = None
        
        # Step 4: Visual Tracking
        await manager.send_status(session_id, "Analyzing visual posture & engagement...", 70)
        analysis_sessions[session_id]["progress"] = 70
        analysis_sessions[session_id]["message"] = "Analyzing visual posture & engagement..."
        try:
            visual_feats = await asyncio.to_thread(extract_visual_features, video_path)
        except Exception as e:
            print(f"Visual feature extraction failed: {e}")
            visual_feats = None

        # Step 5 & 6: Story & Evaluation
        await manager.send_status(session_id, "Computing performance scores...", 90)
        analysis_sessions[session_id]["progress"] = 90
        analysis_sessions[session_id]["message"] = "Computing performance scores..."
        
        curr_trans = (transcript.get("text", "") if isinstance(transcript, dict) else str(transcript or "")).strip()
        story_data = None
        if len(curr_trans.split()) >= 6:
            try:
                story_data = await asyncio.to_thread(extract_story_facts, transcript=curr_trans, person_name="Candidate")
            except Exception as e:
                print(f"Story fact extraction error: {e}")
                story_data = None
        
        eval_data = await asyncio.to_thread(
            compute_deterministic_scores,
            person_name="Candidate",
            transcript=curr_trans,
            story_data=story_data,
            speech_feats=speech_feats,
            visual_feats=visual_feats,
            profile=None
        )
        overall_score, assessment_text = calculate_overall_communication_score(eval_data, profile=None)

        # Telemetry compilation
        pause_count = speech_feats.get("pause_count") if speech_feats else None
        total_pause_duration = speech_feats.get("total_pause_duration_sec") if speech_feats else None
        avg_pause_duration = None
        if total_pause_duration is not None and pause_count is not None and pause_count > 0:
            avg_pause_duration = round(total_pause_duration / pause_count, 2)
        elif total_pause_duration is not None:
            avg_pause_duration = round(total_pause_duration, 2)

        telemetry = {
            "pitch_variation_hz": speech_feats.get("pitch_variation_hz") if speech_feats else None,
            "speaking_rate_wpm": speech_feats.get("speaking_rate_wpm") if speech_feats else None,
            "pause_duration_sec": avg_pause_duration,
            "total_pause_sec": total_pause_duration,
            "pause_count": pause_count,
            "filler_word_count": speech_feats.get("filler_word_count") if speech_feats else None,
            "word_count": speech_feats.get("word_count") if speech_feats else None,
            "face_presence_ratio": visual_feats.get("face_presence_ratio") if visual_feats else None,
            "face_detected": visual_feats.get("face_detected", False) if visual_feats else False,
            "head_movement_count": visual_feats.get("head_movement_count") if visual_feats else None,
            "head_movement_rate_per_min": visual_feats.get("head_movement_rate_per_min") if visual_feats else None,
            "blink_count": visual_feats.get("blink_count") if visual_feats else None,
            "duration_seconds": (visual_feats.get("duration_seconds") if visual_feats else None) or (speech_feats.get("duration_seconds") if speech_feats else None),
        }

        modality_status = {
            "audio": "available" if speech_feats and speech_feats.get("reliability_flag") == "good" else "insufficient",
            "visual": "available" if visual_feats and visual_feats.get("tracking_reliability") == "good" and visual_feats.get("face_detected") else "insufficient",
            "transcript": "available" if len(curr_trans.split()) >= 3 else "insufficient",
        }

        # Extract evidence-backed strengths and growth targets
        strengths = []
        growth_targets = []

        valid_cats = [
            (cat, data) for cat, data in eval_data.items()
            if isinstance(data, dict) and isinstance(data.get("score"), (int, float)) and not isinstance(data.get("score"), bool)
        ]
        valid_cats.sort(key=lambda x: x[1]["score"], reverse=True)

        for cat, data in valid_cats:
            if data["score"] >= 65:
                www = data.get("what_went_well")
                if www and www != "N/A" and www not in strengths:
                    strengths.append(www)

        low_cats = sorted(valid_cats, key=lambda x: x[1]["score"])
        for cat, data in low_cats:
            if data["score"] < 80:
                rec = data.get("practical_recommendation") or data.get("what_needs_improvement")
                if rec and rec != "N/A" and rec not in growth_targets:
                    growth_targets.append(rec)

        if not growth_targets and low_cats:
            rec = low_cats[0][1].get("practical_recommendation") or low_cats[0][1].get("what_needs_improvement")
            if rec and rec != "N/A":
                growth_targets.append(rec)

        if not strengths:
            if valid_cats:
                strengths.append(f"Recorded delivery in {len(valid_cats)} observable multimodal dimension(s).")
            else:
                strengths.append("Baseline recording captured. Ensure audible speech and forward-facing camera framing to evaluate delivery.")

        if not growth_targets:
            growth_targets.append("Maintain clear articulation, natural pacing, and steady framing across extended speaking sessions.")

        completed_payload = {
            "session_id": session_id,
            "status": "completed",
            "progress": 100,
            "message": "Analysis Complete",
            "overall_score": overall_score,
            "assessment_text": assessment_text,
            "strengths": strengths,
            "growth_targets": growth_targets,
            "categories": eval_data,
            "telemetry": telemetry,
            "transcript": curr_trans,
            "modality_status": modality_status,
        }

        analysis_sessions[session_id] = completed_payload
        _save_session_checkpoint(session_id, completed_payload)
        await manager.send_status(session_id, "Analysis Complete", 100)
    except Exception as e:
        err_msg = str(e)
        failed_payload = {
            "session_id": session_id,
            "status": "failed",
            "progress": 0,
            "error": err_msg,
        }
        analysis_sessions[session_id] = failed_payload
        _save_session_checkpoint(session_id, failed_payload)
        await manager.send_status(session_id, f"Error: {err_msg}", 0)

@app.post("/api/analyze")
async def analyze_video(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...)
):
    session_id = str(uuid.uuid4())
    os.makedirs(VIDEO_DIR, exist_ok=True)
    os.makedirs(AUDIO_DIR, exist_ok=True)
    
    # Extract the correct extension (e.g. .webm from live camera, .mp4 from upload)
    ext = os.path.splitext(file.filename)[1] if file.filename else ".mp4"
    if not ext:
        ext = ".mp4"
        
    video_path = os.path.join(VIDEO_DIR, f"upload_{session_id}{ext}")
    with open(video_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    analysis_sessions[session_id] = {
        "session_id": session_id,
        "status": "processing",
        "progress": 0,
        "message": "Upload received. Queuing analysis pipeline...",
    }
    _save_session_checkpoint(session_id, analysis_sessions[session_id])

    # Queue the heavy pipeline in the background!
    background_tasks.add_task(run_real_pipeline, session_id, video_path)
    
    return {"message": "Analysis started asynchronously.", "session_id": session_id}

@app.get("/api/analysis/{session_id}")
async def get_analysis_result(session_id: str):
    if session_id not in analysis_sessions:
        loaded = _load_session_checkpoint(session_id)
        if loaded:
            analysis_sessions[session_id] = loaded
        else:
            raise HTTPException(status_code=404, detail=f"Analysis session {session_id} not found.")
    return analysis_sessions[session_id]
