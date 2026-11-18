# Low-Level Design (LLD)

## Project Title
**Zaira AI — Adaptive AI Interviewer**

**Author:** Santhosh (santhoshgg08@gmail.com)  
**Repository:** [https://github.com/Santhosh082006/zaira-ai](https://github.com/Santhosh082006/zaira-ai)  
**Document Version:** 1.0.0  
**Status:** Approved  

---

## 1. Database Schema / Data Models

Zaira AI uses in-memory session storage with JSON file persistence. Below are the core data models.

### InterviewSession

| Field | Type | Description |
|---|---|---|
| session_id | string | Unique UUID session identifier |
| interview_type | string | "technical", "behavioral", "academic_viva" |
| interview_level | string | "junior", "intermediate", "senior", "principal" |
| technical_domain | string | "Python", "Full Stack Web", "Data Structures", etc. |
| assessment_goals | string[] | ["COMMUNICATION", "PERFORMANCE", "TECHNICAL_DEPTH"] |
| question_history | Question[] | List of all questions asked |
| answer_history | AnswerRecord[] | List of all evaluated answers |
| competency_scores | object | Competency dimension → score mapping |
| completion_status | string | "in_progress", "completed" |
| created_at | datetime | Session creation timestamp |

### Question

| Field | Type | Description |
|---|---|---|
| id | string | Unique question identifier (e.g., "q_py_001") |
| question_text | string | The full question text |
| question_type | string | "technical", "behavioral", "followup" |
| difficulty | int | 1 (Junior) to 4 (Principal) |
| topics | string[] | Related topics (e.g., ["Python", "GIL"]) |
| expected_concepts | string[] | Concepts a good answer should cover |

### AnswerRecord

| Field | Type | Description |
|---|---|---|
| answer_id | string | Unique answer identifier |
| question_id | string | Reference to the question answered |
| transcript | string | Full transcribed text from Whisper |
| overall_answer_quality | float | Score from 0.0 to 100.0 |
| rubric_criteria | RubricCriterion[] | Detailed per-criterion scoring |
| actionable_findings | ActionableFinding[] | Specific improvement suggestions |
| strengths | string[] | Detected strong points |
| areas_to_improve | string[] | Identified weaknesses |

### RubricCriterion

| Field | Type | Description |
|---|---|---|
| criterion_name | string | "Technical Accuracy", "Clarity", etc. |
| max_marks | float | Maximum possible score |
| marks_awarded | float | Actual score given |
| deduction | float | Points deducted |
| evidence_quote | string | Exact quote from candidate's answer |
| reason_for_deduction | string | Why points were deducted |

---

## 2. API Endpoints

### 2.1 Start Interview Session
- **Method:** `POST`
- **Endpoint:** `/api/interview/start`
- **Request Body:**
  ```json
  {
    "interview_type": "technical",
    "interview_level": "intermediate",
    "assessment_goals": ["COMMUNICATION", "PERFORMANCE"],
    "technical_domain": "Python"
  }
  ```
- **Response (200 OK):**
  ```json
  {
    "session_id": "sess_001c85f85f75",
    "current_question": {
      "id": "q_py_001",
      "question_text": "Walk me through the Python GIL...",
      "difficulty": 2,
      "topics": ["Python", "Concurrency"]
    },
    "completion_status": "in_progress",
    "interview_progress": 0.15
  }
  ```

### 2.2 Submit Answer (Audio)
- **Method:** `POST`
- **Endpoint:** `/api/interview/{session_id}/answer/media`
- **Content-Type:** `multipart/form-data`
- **Form Fields:** `question_id` (string), `file` (audio/webm binary)
- **Response (200 OK):**
  ```json
  {
    "session_id": "sess_001c85f85f75",
    "transcript": "The Global Interpreter Lock...",
    "overall_answer_quality": 85.0,
    "structured_evaluation": {
      "rubric_criteria": [...],
      "actionable_findings": [...],
      "strengths": [...],
      "areas_to_improve": [...]
    },
    "next_question": {
      "id": "q_py_followup_002",
      "question_text": "How does asyncio handle concurrency...",
      "difficulty": 3
    },
    "completion_status": "in_progress"
  }
  ```

### 2.3 Generate Avatar Session Token
- **Method:** `POST`
- **Endpoint:** `/api/interview/avatar/token`
- **Response (200 OK):**
  ```json
  {
    "available": true,
    "token": "eyJhbGciOiJIUzI1NiIs...",
    "session_id": "088efb78-e3ab-430c...",
    "avatar_id": "56c84371-a65c-4f11...",
    "voice_id": "b1200469-775a-415b..."
  }
  ```

### 2.4 Synthesize Question Audio
- **Method:** `POST`
- **Endpoint:** `/api/interview/tts`
- **Request Body:**
  ```json
  {
    "text": "Could you walk me through your journey?",
    "audio_format": "pcm24k"
  }
  ```
- **Response (200 OK):**
  ```json
  {
    "status": "success",
    "format": "pcm_s16le",
    "sample_rate": 24000,
    "channels": 1,
    "chunks": ["<base64_pcm_chunk_1>", "<base64_pcm_chunk_2>"]
  }
  ```

### 2.5 Get Interview Report
- **Method:** `GET`
- **Endpoint:** `/api/interview/{session_id}/report`
- **Response (200 OK):** Complete interview report with all scores, transcripts, and findings.

---

## 3. WebSocket Protocol

- **Endpoint:** `ws://localhost:8000/api/ws/interview/{session_id}`

### Client → Server Messages

| Type | Fields | Purpose |
|---|---|---|
| `live_transcript_chunk` | text, is_final, duration_sec | Stream live candidate speech |
| `heartbeat` | timestamp | Keep connection alive (every 15s) |

### Server → Client Messages

| Type | Fields | Purpose |
|---|---|---|
| `connected` | session_id, status | Confirm WebSocket connection |
| `live_feedback` | wpm, pacing_status, coaching_hint | Real-time speaking feedback |
| `question_ready` | question | New adaptive question available |
| `evaluation_streaming` | stage, progress, message | Evaluation progress updates |
| `interview_completed` | session_id, report | Session finished, final report |

---

## 4. Component Architecture

### Frontend Components

```
src/
├── app/
│   └── page.tsx                    # Main page routing
├── components/
│   ├── InterviewDashboard.tsx      # Root interview controller
│   ├── InterviewerAvatar.tsx       # Avatar display (WebRTC / 2D)
│   ├── AudioRecorder.tsx           # Microphone capture and display
│   └── interview/
│       ├── InterviewConfig.tsx     # Session setup form
│       ├── EvaluationPanel.tsx     # Rubric results display
│       └── InterviewCompleted.tsx  # Final report view
├── hooks/
│   ├── useLiveAvatar.ts            # HeyGen WebRTC lifecycle
│   ├── useAvatarVoice.ts           # TTS audio playback
│   └── useInterviewSession.ts     # Session state management
└── lib/
    ├── interviewApi.ts             # REST API client functions
    └── interviewWebSocket.ts       # WebSocket client
```

### Backend Modules

```
backend/
├── api.py                          # FastAPI app, CORS, middleware
├── routes/
│   ├── interview.py                # REST endpoints, TTS, avatar token
│   └── interview_ws.py             # WebSocket handler
└── schemas/
    ├── interview.py                # Pydantic request/response models
    └── interview_ws.py             # WebSocket message schemas

core/
├── interview_controller.py         # Adaptive state machine
├── interview_session.py            # Session entity and storage
├── question_bank.py                # Question catalog
└── competency_map.py               # Competency tracking matrix

services/
├── answer_evaluator_llm.py         # LLM rubric scoring engine
├── speech_to_text.py               # Whisper integration
├── llm_provider.py                 # Multi-provider LLM bridge
└── resume_parser.py                # Resume text extraction
```

---

## 5. Key Algorithms

### 5.1 Adaptive Difficulty Adjustment
The next question difficulty adjusts based on the candidate's score:
- Score ≥ 85 → Increase difficulty by 1 (max 4)
- Score 65–84 → Keep same difficulty
- Score < 65 → Decrease difficulty by 1 (min 1)

### 5.2 Words Per Minute (WPM) Calculation
```
WPM = (Total Words / Speaking Time in Seconds) × 60
```
- WPM < 105 → "too_slow"
- 105 ≤ WPM ≤ 165 → "optimal"
- WPM > 165 → "too_fast"

### 5.3 Interview Stopping Conditions
The interview ends when any of these conditions are met:
1. All target competency dimensions have been assessed with sufficient evidence.
2. The maximum question count (5–7 questions) is reached.
3. The candidate requests to end the session.

### 5.4 Avatar Speech Pipeline
1. Question text is formatted with conversational pauses and phonetic expansions.
2. Edge-TTS generates speech audio (en-US-AvaNeural voice).
3. FFmpeg converts audio to raw PCM (16-bit, 24kHz, mono).
4. PCM audio is base64-encoded and sent to HeyGen WebSocket for lip-synced video rendering.
5. When speech ends, avatar transitions to a natural listening posture.

---

## 6. Error Handling

| Scenario | Handling |
|---|---|
| HeyGen API unavailable | Fallback to local 2D lip-sync engine with Edge-TTS audio |
| LLM provider timeout | Retry with fallback provider (Ollama → Gemini → OpenRouter) |
| Whisper transcription failure | Return error to candidate with option to re-record |
| WebSocket disconnect | Auto-reconnect with exponential backoff |
| Empty candidate audio | Prompt candidate to speak louder or check microphone |
