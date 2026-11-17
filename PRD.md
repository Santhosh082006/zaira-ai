# Product Requirements Document (PRD)

## Project: TruthLens AI & Zaira AI Interviewer Suite
**Document Version:** 1.0.0  
**Status:** Approved  
**Author:** Engineering & Product Team  
**Date:** November 2026  
**Repository:** [https://github.com/Santhosh082006/zaira-ai](https://github.com/Santhosh082006/zaira-ai)

---

## 1. Executive Summary & Vision

**TruthLens AI** is an enterprise-grade multimodal artificial intelligence platform combining two state-of-the-art systems:
1. **Zaira AI — Next-Gen AI Spoken Interviewer**: A real-time, conversational, voice-first interview and viva evaluation engine. It pairs a photorealistic virtual interviewer with real-time lip-synchronization, dynamic competency probing, live acoustic and visual telemetry, and evidence-grounded rubric scoring.
2. **Multimodal Consistency & Truth Analyzer**: An objective cross-session narrative analysis suite designed to detect semantic contradictions, timeline discrepancies, and vocal/visual behavioral variations across multiple candidate statements or deposition recordings.

The vision is to eradicate bias, anxiety, and subjectivity from technical vivas and professional job interviews through transparent, multi-dimensional, and evidence-grounded AI evaluation.

---

## 2. Problem Statement

1. **Subjectivity & Human Fatigue in High-Stakes Assessments**: Manual technical interviews and academic vivas suffer from evaluator inconsistency, interviewer fatigue, implicit bias, and lack of objective audit trails.
2. **Disjointed Non-Verbal & Audio Feedback**: Existing AI interview bots rely on generic text chat or unconvincing robotic text-to-speech with no natural conversational presence or lip synchronization.
3. **Absence of Real-Time Adaptive Guidance**: Candidates receive zero feedback on pacing, filler words, or conceptual omissions while speaking, preventing them from recalibrating mid-answer.
4. **Shallow Keyword Matching**: Conventional ATS and screening tools match keywords without analyzing reasoning structure, practical depth, or evidentiary corroboration.

---

## 3. User Personas & Target Audience

| Persona | Role | Key Goals & Needs |
| :--- | :--- | :--- |
| **Candidate / Student (Priyanka)** | Student or Engineer taking a technical viva / job interview | Seamless browser experience, human-like empathetic interviewer, clear question prompts, transparent scoring with actionable improvement advice. |
| **Academic Evaluator / Examiner (Kalvium)** | Instructor or Viva Panelist | Standardized competency coverage, verified git repository grounding, cheat-proof telemetry, objective score rubric. |
| **Talent Acquisition Lead** | Enterprise Technical Recruiter | Standardized technical interviews across thousands of candidates, automated transcript audit logs, competency radar charts. |

---

## 4. User Journeys & Scenarios

### Scenario A: Technical Adaptive Viva Session
1. **Candidate Initialization**: Candidate selects an interview category (*Job Interview, Academic Viva, Technical Deep Dive*) and difficulty level (*Junior, Intermediate, Senior, Principal*).
2. **Avatar Spoken Articulation**: Zaira speaks the introductory greeting and calibrated opening question prompt aloud using synchronized 2D/WebRTC lip movements.
3. **Attentive Listening & Recording**: Candidate speaks through the microphone and camera. Live soundwave bars and in-flight telemetry monitor pace, word count, and speech energy.
4. **Deep Semantic Analysis**: Upon conclusion, Zaira processes the candidate's speech via on-device Whisper STT and evaluates it against an 8-dimension rubric using local/cloud LLMs.
5. **Adaptive Follow-Up Inquiry**: If a conceptual gap is detected, Zaira formulates a targeted follow-up question.
6. **Holistic Audit Report**: Upon interview conclusion, an exhaustive report is generated with rubric scores, transcript quotes, actionable findings, and competency radar visualization.

---

## 5. Scope & MoSCoW Feature Prioritization

### Must Have (P0)
- **Real-Time Synchronized Virtual Interviewer**: Real-time avatar articulation with audio-synchronized lip motion and natural closed-mouth resting state during candidate listening.
- **Adaptive Question Generator**: Stateful questioning controller dynamically selecting questions based on previous answers, competency matrices, and difficulty level.
- **On-Device Speech Transcription**: High-accuracy local speech-to-text powered by OpenAI Whisper.
- **Evidence-Grounded Rubric Evaluation**: Scoring engine generating numeric grades (0–100), criteria breakdowns (Technical Accuracy, Relevance, Structure, Clarity, Evidence), and verbatim quote extraction.
- **Real-Time WebSocket Telemetry**: Streaming live feedback on words per minute (WPM), pause durations, and coaching hints.
- **Structured Report Generation**: Comprehensive final audit exportable in JSON and visually rendered in dashboard.

### Should Have (P1)
- **LiveAvatar Lite WebRTC Integration**: Ultra-low-latency real-time video stream powered by HeyGen LiveAvatar Lite with PCM 24kHz mono audio streaming.
- **Client-Side Anatomical Viseme Engine**: Zero-dependency 5-state anatomical mouth blend fallback for 100% offline local deployments.
- **Resume & Job Description Grounding**: PDF/text document parsing to personalize questions to the candidate's actual projects.

### Could Have (P2)
- **Multimodal Consistency Comparison Studio**: Streamlit video comparison studio analyzing video facial landmarks and vocal pitch variability across two separate sessions.
- **Eye Contact & Face Presence Tracking**: Visual telemetry tracking candidate face orientation and gaze stability.

### Won't Have (P3 - Out of Scope for v1)
- Autonomous hiring/rejection decisions (the tool is strictly decision-support and evaluative).
- Real-time biometric stress lie-detection claims.

---

## 6. Functional Requirements

### 6.1 Authentication & Configuration Module
- **FR-1.1**: The system must operate without mandatory login for candidate ease, utilizing unique UUID session identifiers.
- **FR-1.2**: Support configurable interview types: `Job Interview`, `Academic Viva`, `Technical Deep Dive`, `Behavioral / Leadership`.
- **FR-1.3**: Support configurable domain focus: `Python`, `Full Stack Web`, `Data Structures & Algorithms`, `System Design`, `DevOps`.

### 6.2 Conversational Avatar & Audio Articulation
- **FR-2.1**: The system must synthesize speech from text using Microsoft Edge-TTS or HeyGen LiveAvatar Lite.
- **FR-2.2**: Spoken text must undergo conversational cadence formatting (expanding acronyms like "API" to "A-P-I", inserting conversational pauses `...`).
- **FR-2.3**: Avatar mouth movement must be physically bound to instantaneous audio energy (0.0 to 1.0) and return to a natural resting smile upon speech completion.
- **FR-2.4**: Candidate must have the option to skip question audio or replay the examiner prompt.

### 6.3 Candidate Ingestion & Real-Time Feedback
- **FR-3.1**: Browser audio recording using `MediaRecorder` API encoded in `audio/webm` or `audio/wav`.
- **FR-3.2**: WebSocket channel (`/api/ws/interview/{session_id}`) delivering live candidate speech updates to the server.
- **FR-3.3**: Server-driven `live_feedback` events emitted every 250ms reporting current WPM, pace status (`too_fast`, `optimal`, `too_slow`), and real-time coaching suggestions.

### 6.4 Evaluation & Follow-Up Engine
- **FR-4.1**: Audio transcription executed via OpenAI Whisper with fallback to browser SpeechRecognition.
- **FR-4.2**: Evaluation completed against five mandatory dimensions: Technical Depth, Logical Structure, Practical Evidence, Relevance, and Communication Clarity.
- **FR-4.3**: Each finding must include: `finding`, `supporting_evidence` (direct quote), `explanation`, and `specific_correction` with a model answer.
- **FR-4.4**: The adaptive state machine must terminate when either target competency saturation is achieved or the maximum question threshold (typically 5–7 questions) is reached.

---

## 7. Non-Functional Requirements (NFRs)

| Metric | Requirement |
| :--- | :--- |
| **Latency** | Question audio synthesis start time < 800ms; Evaluation processing < 4.0s. |
| **Audio Quality** | Edge-TTS / WebRTC speech streamed in PCM 16-bit, 24,000 Hz, Mono. |
| **Reliability** | Automatic graceful fallback from WebRTC LiveAvatar to local 2D anatomical viseme animation without user-visible crash. |
| **Compatibility** | Modern Evergreen Browsers (Chrome 110+, Edge 110+, Safari 16+, Firefox 115+). |
| **Privacy & Security** | Audio recordings processed locally or in isolated memory; API keys secured exclusively in backend `.env`. |
| **Offline Capability** | Full stack operable locally with Ollama (`qwen2.5:7b`), Whisper base model, and client-side viseme rendering. |

---

## 8. Success Metrics & Key Performance Indicators (KPIs)

1. **Session Completion Rate**: $\ge 92\%$ of started interview sessions successfully proceed to final report generation.
2. **Transcription Word Error Rate (WER)**: $< 8.5\%$ across technical terminology and programming syntax.
3. **Evaluation Groundedness**: $100\%$ of deducted points accompanied by an exact evidence excerpt from the candidate's transcript.
4. **Avatar Sync Accuracy**: Viseme frame transitions synchronized within 45ms of acoustic audio energy peaks.
