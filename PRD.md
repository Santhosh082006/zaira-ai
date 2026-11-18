# Product Requirements Document (PRD)

## Project Title
**Zaira AI — Adaptive AI Interviewer**

**Author:** Santhosh (santhoshgg08@gmail.com)  
**Repository:** [https://github.com/Santhosh082006/zaira-ai](https://github.com/Santhosh082006/zaira-ai)  
**Document Version:** 1.0.0  
**Status:** Approved  

## Project Overview
Zaira AI is an intelligent, real-time AI-powered interview and viva assessment platform. It conducts spoken technical interviews with a photorealistic virtual interviewer avatar, dynamically adapts questions based on the candidate's answers, provides live speech feedback, and generates structured evaluation reports with evidence-grounded scores.

---

## Problem Statement
Traditional technical interviews and academic viva assessments are inconsistent, subjective, and prone to evaluator bias and fatigue. Candidates receive no real-time feedback on their communication quality while answering, and existing AI interview tools rely on flat text chat with no natural conversational presence. There is no affordable, offline-capable platform that combines a lifelike spoken interviewer, adaptive questioning, real-time speech coaching, and objective rubric-based evaluation.

---

## Target Audience / User Personas

| Persona | Description |
|---|---|
| **Student / Candidate** | A student or engineer preparing for a technical viva or job interview who needs a realistic practice environment with structured feedback. |
| **Academic Evaluator / Instructor** | A professor or mentor who wants standardized, evidence-grounded assessment of student understanding with audit-ready transcripts. |
| **Recruiter / Hiring Manager** | A hiring professional who wants consistent, scalable technical screening with competency radar charts and actionable reports. |

---

## User Stories

1. **As a candidate**, I want to select my interview category (Job Interview, Academic Viva, Technical Deep Dive) and difficulty level so that the session is tailored to my needs.
2. **As a candidate**, I want to see and hear a lifelike avatar interviewer speak the questions naturally so that the experience feels like a real conversation.
3. **As a candidate**, I want to answer questions using my microphone so that my spoken responses are captured and evaluated.
4. **As a candidate**, I want to see real-time feedback on my speaking pace (WPM), pausing, and word count so that I can adjust while answering.
5. **As a candidate**, I want to receive a detailed evaluation report with rubric scores, strengths, weaknesses, and improvement suggestions after the interview so that I know exactly where to improve.
6. **As an evaluator**, I want the system to generate adaptive follow-up questions based on the candidate's answers so that it probes deeper into knowledge gaps.
7. **As an evaluator**, I want every deducted score point backed by an exact evidence quote from the candidate's transcript so that the evaluation is objective and auditable.
8. **As a recruiter**, I want to view competency radar charts and structured JSON reports so that I can compare candidates consistently.

---

## Core Features (MVP Scope)

### Must Have (P0)
- Real-time AI interviewer avatar with audio-synchronized lip movements.
- Adaptive question generation based on candidate performance.
- On-device speech-to-text using OpenAI Whisper.
- Evidence-grounded 5-dimension rubric evaluation (Technical Accuracy, Relevance, Structure, Clarity, Evidence Quality).
- Real-time WebSocket telemetry (WPM, pacing status, coaching hints).
- Structured final interview report.

### Should Have (P1)
- HeyGen LiveAvatar Lite WebRTC integration for photorealistic video.
- Resume and job description upload for personalized questions.
- Interview session replay and history.

### Could Have (P2)
- Multi-session consistency comparison.
- Eye contact and face presence tracking.

---

## Acceptance Criteria

1. The interviewer avatar speaks the opening question within 3 seconds of session start.
2. The system accurately transcribes candidate audio with less than 10% word error rate.
3. Each evaluation includes at least one evidence quote per deducted rubric criterion.
4. The adaptive engine generates follow-up questions targeting identified knowledge gaps.
5. The final report includes overall score, rubric breakdown, strengths, weaknesses, and actionable findings.
6. The platform runs fully offline using Ollama (Qwen 2.5:7b) and local Whisper.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 16, React 19, Tailwind CSS v4 |
| Backend | Python, FastAPI |
| Speech-to-Text | OpenAI Whisper (on-device) |
| Text-to-Speech | Microsoft Edge-TTS / HeyGen LiveAvatar Lite |
| LLM Provider | Ollama (Qwen 2.5:7b), Google Gemini API, OpenRouter |
| Real-Time Communication | WebSocket, WebRTC |
| Database | In-memory session store with JSON file persistence |

---

## Non-Functional Requirements

| Requirement | Target |
|---|---|
| Latency | Question audio synthesis < 800ms; Evaluation processing < 4s |
| Compatibility | Chrome 110+, Edge 110+, Safari 16+, Firefox 115+ |
| Offline Capability | Full stack operable with local Ollama and Whisper |
| Privacy | Audio processed locally; API keys stored only in backend .env |

---

## Out of Scope (v1)
- Autonomous hiring or rejection decisions.
- Real-time biometric lie detection.
- Multi-language interview support.
- Mobile native application.

---

## Success Metrics

1. Session completion rate ≥ 92%.
2. Transcription word error rate < 10%.
3. 100% of score deductions backed by evidence quotes.
4. Avatar lip-sync accuracy within 50ms of audio peaks.
