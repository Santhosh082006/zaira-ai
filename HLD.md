# High-Level Design (HLD)

## Project: TruthLens AI & Zaira AI Interviewer Suite
**Document Version:** 1.0.0  
**Status:** Approved  
**Author:** Engineering & Product Team  
**Date:** November 2026  
**Repository:** [https://github.com/Santhosh082006/zaira-ai](https://github.com/Santhosh082006/zaira-ai)

---

## 1. System Context & Overview

TruthLens AI & Zaira AI provide a real-time, multimodal spoken interview assessment architecture designed to simulate an elite technical panelist. The system comprises two collaborative layers:
1. **Interactive Spoken Interviewer (Zaira AI)**: A reactive front-facing client with an audio-synchronized virtual interviewer, live audio recorder, bidirectional WebSocket telemetry, and adaptive questioning.
2. **Analytical & Evaluative Backend**: A high-performance Python FastAPI engine orchestrating OpenAI Whisper transcription, multi-provider LLM evaluations, adaptive state machines, and real-time speech prosody synthesis.

```mermaid
flowchart TD
    subgraph ClientLayer ["Client Presentation Layer (Next.js 16 / React 19)"]
        UI["Interview Dashboard & Config"]
        AvatarUI["InterviewerAvatar (WebRTC / 2D Viseme)"]
        RecorderUI["AudioRecorder & Telemetry Console"]
        EvalUI["EvaluationPanel & Audit Report"]
    end

    subgraph GatewayLayer ["API & Communication Layer"]
        REST["FastAPI REST Endpoints (:8000)"]
        WS["WebSocket Server (/api/ws/interview/{sid})"]
    end

    subgraph CoreEngine ["Zaira Adaptive Analytical Core"]
        Controller["InterviewController (State Machine)"]
        SessionMgr["InterviewSession (State & History)"]
        QBank["QuestionBank & CompetencyMap"]
        EvalEngine["AnswerEvaluator & Rubric Grader"]
        TelemetryEngine["LiveFeedbackAnalyzer (WPM, Pacing)"]
    end

    subgraph AudioVisual ["Speech & Avatar Services"]
        EdgeTTS["Edge-TTS Neural Synthesizer"]
        PCMConverter["FFmpeg PCM 24kHz Converter"]
        LiveAvatarAPI["HeyGen LiveAvatar Lite WebRTC"]
        WhisperSTT["OpenAI Whisper (On-Device STT)"]
    end

    subgraph LLMBridge ["Multi-Provider LLM Gateway"]
        OllamaLocal["Ollama (Qwen 2.5:7b / Local)"]
        CloudLLM["OpenRouter / Google Gemini API"]
    end

    UI --> REST
    UI --> WS
    AvatarUI <--> LiveAvatarAPI
    RecorderUI --> WS
    RecorderUI --> REST

    REST --> Controller
    WS --> TelemetryEngine
    Controller --> SessionMgr
    Controller --> QBank
    Controller --> EvalEngine

    Controller --> EdgeTTS
    EdgeTTS --> PCMConverter
    PCMConverter --> LiveAvatarAPI
    
    EvalEngine --> WhisperSTT
    EvalEngine --> LLMBridge
    LLMBridge --> OllamaLocal
    LLMBridge --> CloudLLM
```

---

## 2. Subsystem Architecture

### 2.1 Frontend Client Subsystem (Next.js 16 + React 19)
- **Role**: Drives candidate interaction, renders the virtual interviewer, captures webcam and microphone streams, and renders real-time rubric scoreboards.
- **Key Modules**:
  - `InterviewDashboard.tsx`: Root controller managing interview phases (`CONFIG`, `READY`, `PROCESSING`, `ANSWER_RESULT`, `COMPLETED`).
  - `InterviewerAvatar.tsx`: Synchronized avatar component rendering either the WebRTC HeyGen stream or the local 2D anatomical viseme blend engine with Web Audio frequency analysis.
  - `AudioRecorder.tsx`: High-resolution audio capture using `MediaRecorder`, soundwave canvas visualizer, and streaming live speech transcript update hooks.
  - `useLiveAvatar.ts`: Custom React hook encapsulating HeyGen LiveAvatar Lite WebRTC lifecycle, WebSocket audio streaming (`agent.speak`), and attentive listening states.
  - `useInterviewSession.ts`: Manages REST calls and real-time WebSocket state synchronizations with the backend.

### 2.2 Backend Application Subsystem (FastAPI)
- **Role**: High-concurrency async web server handling REST session contracts, WebSocket telemetry, audio transcoding, and avatar authentication tokens.
- **Key Modules**:
  - `backend/api.py`: FastAPI application root with CORS middleware, WebSocket connection manager, and error handlers.
  - `backend/routes/interview.py`: Core REST endpoints (`/start`, `/answer`, `/retry`, `/tts`, `/avatar/token`, `/report`).
  - `backend/routes/interview_ws.py`: Real-time duplex WebSocket endpoint broadcasting `live_feedback`, `evaluation_streaming`, and `question_ready` events.
  - `backend/schemas/`: Pydantic models enforcing strict contract validations.

### 2.3 Conversational Avatar & Audio Subsystem
- **Role**: Converts written interview questions into natural conversational speech and physically animates the avatar.
- **Processing Pipeline**:
  1. **Text Formatting**: `format_conversational_speech_flow` expands acronyms phonetically and injects breath pauses.
  2. **Neural Speech Generation**: Edge-TTS generates high-fidelity audio (`en-US-AvaNeural`).
  3. **PCM 24k Transcoding**: ImageIO-FFmpeg converts audio into raw 16-bit, 24,000 Hz, mono PCM chunks.
  4. **Avatar Articulation**:
     - *Mode A (LiveAvatar Lite WebRTC)*: Base64 PCM chunks streamed to HeyGen WebSocket (`agent.speak` $\rightarrow$ `agent.speak_end`), rendering real-time synchronized video via LiveKit WebRTC.
     - *Mode B (Local 2D Viseme Engine)*: Client Web Audio Analyser measures speech energy at 60 FPS, dynamically interpolating between 5 anatomical mouth visemes (`zaira-viseme-0.png` to `4.png`).

### 2.4 Analytical & Adaptive Core Subsystem
- **Role**: Stateful intelligence controlling interview progression, difficulty calibration, and rubric scoring.
- **Key Modules**:
  - `core/interview_controller.py`: Stateful controller executing the dynamic questioning loop and stopping condition logic.
  - `core/question_bank.py`: Dynamic question catalog indexing technical, behavioral, and architectural inquiries across difficulty tiers.
  - `core/competency_map.py`: Matrix tracking competency demonstration across 8 vectors (e.g., Code Quality, System Architecture, Problem Solving).
  - `core/answer_evaluator.py`: Multi-dimensional evaluation engine analyzing candidate transcripts for factual depth, structure, and clarity.

---

## 3. End-to-End Sequence Workflows

### 3.1 Session Start & Avatar Question Articulation

```mermaid
sequenceDiagram
    autonumber
    actor Candidate
    participant UI as Next.js Client
    participant API as FastAPI Backend
    participant LiveAvatar as HeyGen / WebRTC
    participant TTS as Edge-TTS & FFmpeg

    Candidate->>UI: Select Category & Level -> Click "Initialize Session"
    UI->>API: POST /api/interview/avatar/token
    API-->>UI: { available: true, token: JWT, session_id }
    UI->>LiveAvatar: Connect WebRTC (LiveAvatarSession.start)
    LiveAvatar-->>UI: SESSION_STREAM_READY (Video Track Attached)
    
    UI->>API: POST /api/interview/start { category, level }
    API-->>UI: { session_id, current_question }
    
    UI->>API: POST /api/interview/tts { text, format: "pcm24k" }
    API->>TTS: Synthesize Speech & Convert to PCM 24k
    TTS-->>API: Base64 Chunks
    API-->>UI: { chunks: [b64_1, b64_2, ...] }
    
    UI->>LiveAvatar: WS send "agent.speak" + chunks
    UI->>LiveAvatar: WS send "agent.speak_end"
    LiveAvatar-->>UI: Render Synchronized Speaking Video
    LiveAvatar-->>UI: Event: AVATAR_SPEAK_ENDED
    UI->>LiveAvatar: session.startListening() (Mouth naturally closes)
    UI-->>Candidate: Transition to "Ready to Answer"
```

### 3.2 Candidate Recording & Live Telemetry Loop

```mermaid
sequenceDiagram
    autonumber
    actor Candidate
    participant UI as Next.js AudioRecorder
    participant WS as Backend WebSocket
    participant Analyzer as LiveFeedbackAnalyzer

    Candidate->>UI: Speaks Answer into Microphone
    loop Every 250ms Audio Chunk
        UI->>UI: Calculate instantaneous vocal energy
        UI->>WS: { type: "live_transcript_chunk", words, duration }
        WS->>Analyzer: Process Speech Cadence & Terminology
        Analyzer-->>WS: Telemetry (WPM, Pacing, Coverage)
        WS-->>UI: { type: "live_feedback", wpm: 135, pacing: "optimal" }
        UI-->>Candidate: Update soundwave bars & pacing indicators
    end
    Candidate->>UI: Concludes speech -> Click "Submit Answer"
```

### 3.3 Answer Evaluation & Adaptive Follow-Up Questioning

```mermaid
sequenceDiagram
    autonumber
    participant UI as Next.js Client
    participant API as FastAPI Backend
    participant STT as Whisper STT
    participant Evaluator as AnswerEvaluator
    participant Controller as InterviewController

    UI->>API: POST /api/interview/{sid}/answer/media (audio.webm)
    API->>STT: Transcribe Audio File
    STT-->>API: Full Candidate Transcript
    API->>Evaluator: Evaluate Transcript against 5-Dimension Rubric
    Evaluator-->>API: { overall_quality: 84, rubric_criteria, actionable_findings }
    
    API->>Controller: Register Answer & Check Stopping Conditions
    alt Gaps Detected & Max Questions Not Reached
        Controller-->>API: Generate Adaptive Follow-Up Question
        API-->>UI: { completion_status: "in_progress", next_question }
        UI-->>UI: Articulate Follow-up Question via Avatar
    else Competency Saturated or Max Questions Reached
        Controller-->>API: Final Assessment Decision: "completed"
        API-->>UI: { completion_status: "completed", final_report }
        UI-->>UI: Render InterviewCompleted Report & Radar Charts
    end
```

---

## 4. Data Architecture & Storage Strategy

- **In-Memory Active Session Store**: Thread-safe session registry (`InterviewSessionRegistry`) holding active question chains, candidate transcripts, audio blobs, and rubric results.
- **Local Persistence & Serialization**: Completed interview sessions serialized to disk in `.sessions/{session_id}.json` with full audit logs and execution traces.
- **Pre-compiled Question Bank**: Stored in `core/questions.json` containing standardized multi-difficulty question items with targeted topics, expected concepts, and rubric criteria.

---

## 5. Security & Isolation Architecture

1. **Zero Secret Leakage**: `HEYGEN_API_KEY`, `OPENROUTER_API_KEY`, and `GEMINI_API_KEY` reside exclusively in the backend `.env`. The frontend client receives short-lived, single-use JWT session tokens with strictly scoped WebRTC room access.
2. **CORS Hardening**: Explicit origin binding allowing requests from `http://localhost:3000` with credentials support.
3. **Sandbox Compliance**: Fallback mechanisms handle network-restricted environments by defaulting to local Ollama and 2D viseme animation without external dependencies.
