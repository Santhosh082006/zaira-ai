# TruthLens AI

TruthLens AI is a multimodal story consistency analyzer. It automates the structured comparison of narrative accounts provided by two different people (Person A and Person B) describing the same event. 

By extracting structured events and claims from transcripts and applying deterministic semantic matching, TruthLens AI reliably highlights matches, conflicts, and missing information. It also extracts behavioral speech and visual signals to serve as supporting context.

**⚠️ IMPORTANT LIMITATIONS**
- The system **compares information** between accounts.
- It **does not determine truthfulness or deception**.
- It **does not produce deception or credibility scores**.
- Speech and visual signals are **supporting observations only** and must not be treated as proof of lying.

---

## Core Workflow

TruthLens AI follows a highly structured, strict five-step pipeline:

1. **Provide Accounts**: Record or enter Person A and Person B's accounts.
2. **Analyze Stories**: Extract specific events, claims, times, and locations from the transcripts.
3. **Compare Information**: Run timeline and claim-level semantic comparison.
4. **Review Evidence**: Review matches, partial matches, conflicts, missing info, and unknowns.
5. **Export Report**: Download the deterministic Evidence & Consistency Report (PDF).

## Main Features

- **Multimodal Input**: Supports direct microphone recording, local audio file playback, and webcam video uploads.
- **Local Transcription**: Uses OpenAI's Whisper model (running locally on-device) to transcribe spoken accounts.
- **Structured Story Analysis**: Uses LLMs to deterministically map raw text into discrete schema-validated events and claims.
- **Semantic Comparison Engine**: Intelligently identifies agreements and discrepancies between timelines without relying exclusively on exact keyword matching.
- **Explainability Layer**: Generates concrete, deterministic explanations pointing directly back to the `source_text` for every match or conflict.
- **Behavioral Signal Extraction**: Optionally measures acoustic speech features (pitch, energy, pauses) and visual facial features (tracking, blinks, head movements).
- **Downloadable Reports**: Generates a strictly formatted, objective PDF evidence report.
- **Demo Mode**: One-click population of deterministic, fictional scenarios and generated TTS audio to seamlessly demonstrate the complete pipeline.

## Technology Stack

- **Frontend**: Streamlit
- **Transcription**: `openai-whisper`
- **LLM Integration**: `google-generativeai`, `openai`, `requests` (Ollama), `python-dotenv`
- **Audio Processing**: `librosa`, `numpy`
- **Visual Processing**: `opencv-python-headless`, `mediapipe`
- **Report Generation**: `fpdf2`

---

## Project Structure

```text
TruthLens-ai/
├── app.py                      # Main Streamlit application
├── requirements.txt            # Python dependencies
├── .env.example                # Environment variable templates
├── assets/                     # Project media assets (including demo audio)
├── services/                   # Core application logic
│   ├── llm_provider.py         # Abstraction layer for Gemini/OpenAI/Ollama/OpenRouter
│   ├── story_analyzer.py       # Event and claim extraction
│   ├── story_comparator.py     # Semantic matching and timeline comparison
│   ├── speech_features.py      # Acoustic signal extraction
│   ├── visual_features.py      # Face tracking and visual signal extraction
│   └── report_generator.py     # PDF builder for the consistency report
└── tests/                      # Automated validation suites
```

---

## Installation

1. Clone the repository to your local machine.
2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   # Windows:
   venv\Scripts\activate
   # macOS/Linux:
   source venv/bin/activate
   ```
3. Install the required Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```

### System Dependencies
To run transcription and visual processing, your system must have `ffmpeg` installed.
- **Windows**: `winget install ffmpeg` or `choco install ffmpeg`
- **macOS**: `brew install ffmpeg`
- **Linux**: `sudo apt install ffmpeg`

---

## Environment Setup

TruthLens AI requires an LLM provider to extract structured events. 

1. Copy `.env.example` to a new file named `.env`.
2. Open `.env` and set `LLM_PROVIDER` to your preferred service (`openrouter`, `gemini`, `openai`, or `ollama`).
3. Add your corresponding API key.

*Note: Your `.env` file is ignored by Git. Never commit your API keys.*

---

## Running the Application

Once your virtual environment is active and your `.env` is configured, start the application:

```bash
streamlit run app.py
```
The application will launch in your default web browser at `http://localhost:8501`.

---

## Demo Mode

To instantly demonstrate the application without recording audio:
1. Click **▶️ Load Demo Analysis** at the top right of the application.
2. The system will safely clear any existing session state and populate Person A and Person B with a fictional everyday scenario.
3. The demo injects locally generated, deterministic `.wav` speech assets.
4. You can then click **Transcribe**, **Analyze Story**, and **Analyze Speech Signals** to watch the real pipeline process the demo data.

*(Note: Demo Mode uses fictional sample data for demonstration purposes only).*

---

## Optional Speech Signals

If an audio recording is provided (either recorded live or via Demo Mode), you can click **Analyze Speech Signals**. The system uses `librosa` to extract:
- Word Count & Duration
- Speaking Rate (WPM)
- Filler Words & Pause Count
- Pitch (F0 Mean & Variance)
- Energy (dB)

## Optional Visual Signals

If a video file is uploaded, you can click **Analyze Visual Signals**. The system uses `mediapipe` to track facial mesh data and extract:
- Face Presence & Tracking Reliability
- Blink Count
- Head Movements

*Note: Video assets are not included in Demo Mode to avoid unnecessary repository bloat. The system gracefully degrades and displays "No visual data available."*

---

## PDF Report Export

After both stories are analyzed and the comparison is complete, you can generate a **PDF Evidence & Consistency Report**. 
- The report is built natively using `fpdf2`.
- It preserves all extracted `source_text` to ensure strict traceability back to the original transcript.
- It automatically pulls in Speech and Visual metrics if they were processed. 
- It maintains objective, neutral language describing *information differences*, enforcing the application's strict rule against determining truth/deception.
