# TruthLens AI & Zaira AI Interviewer Suite

TruthLens AI is a dual-engine multimodal AI platform combining:
1. **Zaira AI — Next-Gen AI Interviewer**: A real-time, speech-first AI interview assessment system featuring a photorealistic 2D avatar with real-time audio-driven lip synchronization, live acoustic analysis, WebSocket streaming, and automated evaluation.
2. **Multimodal Consistency Analyzer**: An objective narrative and video analysis system for comparing spoken accounts, extracting timeline events, evaluating verbal/non-verbal behavioral signals, and generating structured consistency reports.

---

## ⚡ Quick Start (New Laptop Setup)

### 1. Clone the Repository
```bash
git clone https://github.com/Santhosh082006/zaira-ai.git
cd zaira-ai
```

### 2. Python Environment Setup
Ensure Python 3.10+ and `ffmpeg` are installed.
```bash
# Create and activate virtual environment
python -m venv venv

# Windows:
venv\Scripts\activate
# macOS / Linux:
source venv/bin/activate

# Install all backend and analytical dependencies
pip install -r requirements.txt
```

### 3. Frontend Setup (Zaira AI)
Ensure Node.js 18+ is installed.
```bash
cd frontend
npm install
cd ..
```

### 4. Configure Environment Variables
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
Open `.env` and set your preferred LLM provider (`ollama`, `openrouter`, or `gemini`). For local offline use, install Ollama with `qwen2.5:7b`.

---

## 🚀 Running the Applications

### Option A: One-Click Launcher (Windows)
Double-click `START_ZAIRA.bat` or run:
```cmd
START_ZAIRA.bat
```
This automatically starts:
- **FastAPI Backend** on `http://127.0.0.1:8000`
- **Next.js Frontend** on `http://127.0.0.1:3000`
- Opens your browser to the Zaira AI Interview dashboard.

### Option B: Manual Start (Any OS)
1. **Start the FastAPI Backend**:
   ```bash
   venv/Scripts/uvicorn backend.api:app --host 0.0.0.0 --port 8000
   ```
2. **Start the Next.js Frontend**:
   ```bash
   cd frontend
   npm run dev -- -H 127.0.0.1 -p 3000
   ```
3. Open `http://127.0.0.1:3000` in your browser.

### Option C: Streamlit Multimodal Consistency Studio
To run the original video/audio comparison studio:
```bash
streamlit run app.py
```
Opens in your browser at `http://localhost:8501`.

---

## 🎯 Architecture Overview

```text
Truth-Lens-ai/
├── START_ZAIRA.bat             # One-click Windows launcher for full suite
├── requirements.txt            # Python dependencies (FastAPI, Streamlit, ML, Edge-TTS)
├── .env.example                # Canonical environment template
├── backend/                    # FastAPI High-Performance Backend
│   ├── api.py                  # Real API server, WebSockets & health checks
│   ├── routes/                 # REST endpoints (/interview, /tts, /avatar/token)
│   └── schemas/                # Pydantic v2 data models & request/response contracts
├── frontend/                   # Next.js 16 (React 19, Tailwind v4) Web Application
│   ├── src/app/                # App router and main pages
│   ├── src/components/         # UI components
│   │   ├── InterviewDashboard.tsx  # Adaptive interview session manager
│   │   ├── InterviewerAvatar.tsx   # 2D real-time audio-driven lip-sync avatar
│   │   ├── AudioRecorder.tsx       # Live speech-to-text candidate recording console
│   │   └── CompareDashboard.tsx    # Multimodal cross-comparison dashboard
│   ├── public/images/          # Avatar portraits & 5 anatomical viseme frames
│   └── public/models/          # 3D Ready Player Me assets & acoustic models
├── core/                       # Core Analytical & Adaptive Controllers
│   ├── interview_controller.py # Adaptive questioning state machine
│   ├── interview_session.py    # Active session lifecycle & evaluation storage
│   ├── question_bank.py        # Curated technical & behavioral question catalog
│   └── questions.json          # Standardized question database
├── services/                   # Deep Learning & AI Inference Services
│   ├── llm_provider.py         # Multi-provider LLM bridge (Ollama, Gemini, OpenRouter)
│   ├── speech_to_text.py       # OpenAI Whisper on-device transcription
│   └── live_feedback_analyzer.py # Real-time coaching signals
├── scripts/                    # Core Generators & Developer Utilities
│   ├── build_standard_questions.py   # Question bank compiler
│   └── render_anatomical_visemes.py  # 2D viseme frame generator
└── tests/                      # Automated validation suites
```

---

## 👩‍💼 Zaira 2D Audio-Driven Lip-Sync Engine

Zaira uses a client-side 2D viseme animation engine:
- **Zero Hallucination / Distortions**: Preserves Zaira's photographic identity, lighting, and facial proportions from `zaira-avatar.png`.
- **Anatomical Visemes**: 5 states (`zaira-viseme-0.png` to `zaira-viseme-4.png`) representing resting closed smile, soft consonants (5px jaw drop), active vowels (10px drop with dental arch and dark oral depth), open vowels (16px drop), and rounded vowels.
- **Real-Time Audio Synchronization**: Web Audio Analyser reads acoustic energy and speech formant frequencies at 60 FPS, actively moving the mouth on syllables and returning to resting closed smile during pauses and when audio completes.
- **Zero Paid Dependencies**: 100% free, runs client-side with Microsoft Edge-TTS delivering high-fidelity voice audio.
