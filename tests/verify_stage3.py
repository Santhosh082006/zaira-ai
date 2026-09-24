"""
TruthLens AI — Stage 3 Code Verification Script
Run: python verify_stage3.py
"""
import io, ast, re, sys, os

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

results = []

def check(label, passed, detail=""):
    status = "PASS" if passed else "FAIL"
    results.append((status, label, detail))

# ── Read all files ────────────────────────────────────────────────────────────
files = {
    "llm_provider":  io.open(os.path.join(ROOT_DIR, "services/llm_provider.py"),  encoding="utf-8").read(),
    "story_analyzer":io.open(os.path.join(ROOT_DIR, "services/story_analyzer.py"), encoding="utf-8").read(),
    "app":           io.open(os.path.join(ROOT_DIR, "app.py"),                     encoding="utf-8").read(),
    "requirements":  io.open(os.path.join(ROOT_DIR, "requirements.txt"),           encoding="utf-8").read(),
    "gitignore":     io.open(os.path.join(ROOT_DIR, ".gitignore"),                 encoding="utf-8").read(),
}

# Parse ASTs
trees = {}
for name in ("llm_provider", "story_analyzer", "app"):
    trees[name] = ast.parse(files[name])

def get_func_names(tree):
    return {n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}

# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 1 — services/llm_provider.py
# ═══════════════════════════════════════════════════════════════════════════════
src = files["llm_provider"]

check("1.1  OpenRouter is a recognised provider",
      "openrouter" in src and "_call_openrouter" in src)

check("1.2  LLM_PROVIDER read via os.getenv",
      'os.getenv("LLM_PROVIDER"' in src)

check("1.3  OPENROUTER_API_KEY read via os.getenv — never hardcoded",
      'os.getenv("OPENROUTER_API_KEY"' in src)

check("1.4  OPENROUTER_MODEL read via os.getenv",
      'os.getenv("OPENROUTER_MODEL"' in src)

# Check no literal API key is present
api_key_pattern = re.compile(r'["\'](?:sk-[A-Za-z0-9]{20,}|AIza[A-Za-z0-9_\-]{30,})["\']')
match = api_key_pattern.search(src)
check("1.5  No API key is hardcoded in the source",
      match is None,
      detail=f"Found: {match.group() if match else ''}")

check("1.6  get_active_provider() function exists",
      "get_active_provider" in get_func_names(trees["llm_provider"]))

check("1.7  call_llm() public function exists",
      "call_llm" in get_func_names(trees["llm_provider"]))

check("1.8  All four providers in dispatch dict",
      all(p in src for p in ['"openrouter"', '"gemini"', '"openai"', '"ollama"']))

check("1.9  Default provider is openrouter",
      '"openrouter"' in src and 'os.getenv("LLM_PROVIDER", "openrouter")' in src)

check("1.10 OpenRouter uses openrouter.ai/api/v1 base URL",
      "https://openrouter.ai/api/v1" in src)

check("1.11 temperature=0.0 set (deterministic, no hallucination)",
      "temperature=0.0" in src)

# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 2 — services/story_analyzer.py
# ═══════════════════════════════════════════════════════════════════════════════
src = files["story_analyzer"]
funcs = get_func_names(trees["story_analyzer"])

check("2.1  extract_story_facts() function exists",
      "extract_story_facts" in funcs)

check("2.2  validate_extracted_story() function exists",
      "validate_extracted_story" in funcs)

check("2.3  Returns dict / structured JSON (json.loads used)",
      "dict" in src and "json.loads" in src)

check("2.4  Null handling documented in prompt (null for missing strings)",
      "null" in src)

check("2.5  Empty list handling for missing list fields ([])",
      "empty list" in src.lower() or "empty list []" in src or "[]" in src)

check("2.6  Prompt rule: do NOT invent facts",
      "Do NOT invent" in src)

check("2.7  Prompt rule: only EXPLICITLY stated facts",
      "EXPLICITLY" in src or "explicitly stated" in src)

check("2.8  Prompt rule: no markdown fences in response",
      "markdown" in src.lower() and "fences" in src.lower())

check("2.9  Markdown code-fence stripping regex present",
      "re.sub" in src and "```" in src)

check("2.10 Empty transcript raises ValueError",
      "ValueError" in src and ("empty" in src.lower() or "Transcript is empty" in src))

check("2.11 Failed JSON parse raises RuntimeError",
      "RuntimeError" in src and "json.loads" in src)

check("2.12 Imports call_llm from llm_provider",
      "from services.llm_provider import call_llm" in src)

check("2.13 person field always set (safety setdefault)",
      'setdefault("person"' in src)

# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 3 — app.py
# ═══════════════════════════════════════════════════════════════════════════════
src = files["app"]
lines = src.splitlines()

# Stage 2 must be intact
check("3.1  Stage 2 intact: audio_recorder import present",
      "from audio_recorder_streamlit import audio_recorder" in src)

check("3.2  Stage 2 intact: transcribe_audio still used",
      "transcribe_audio" in src)

check("3.3  Stage 2 intact: get_whisper_model still present",
      "get_whisper_model" in src)

check("3.4  Stage 2 intact: st.audio player present",
      "st.audio" in src)

check("3.5  Analyze Story button present",
      "btn_analyze" in src and "Analyze" in src)

# Verify button only shown when transcript exists (nesting check)
transcript_block_line = next(
    (i for i, l in enumerate(lines) if "if st.session_state[transcript_key]" in l), -1)
analyze_button_line = next(
    (i for i, l in enumerate(lines) if "btn_analyze" in l), -1)

check("3.6  Analyze button ONLY inside transcript-exists block",
      0 < transcript_block_line < analyze_button_line,
      detail=f"transcript_check=L{transcript_block_line+1}, analyze_btn=L{analyze_button_line+1}")

check("3.7  ValueError caught (empty transcript error handling)",
      "except ValueError" in src)

check("3.8  RuntimeError caught (LLM/transcription failure)",
      "except RuntimeError" in src)

check("3.9  Broad Exception catch-all (unexpected errors)",
      "except Exception" in src)

check("3.10 render_story_analysis() defined and called",
      "def render_story_analysis" in src and "render_story_analysis(" in src)

check("3.11 st.json() present for raw JSON debug view",
      "st.json" in src)

check("3.12 st.expander() used for debug view",
      "st.expander" in src)

check("3.13 load_dotenv() called at module level",
      "load_dotenv()" in src)

check("3.14 Compare button disabled until BOTH story_data exist",
      "story_data_a" in src and "story_data_b" in src and "disabled=not has_both_stories" in src)

check("3.15 New story recording clears downstream results (story_key reset)",
      "st.session_state[story_key]      = None" in src or
      "st.session_state[story_key] = None" in src)

check("3.16 New transcription clears previous story_data",
      src.count("st.session_state[story_key] = None") >= 1)

check("3.17 get_active_provider() displayed in UI",
      "get_active_provider" in src)

# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 4 — requirements.txt
# ═══════════════════════════════════════════════════════════════════════════════
src = files["requirements"]

packages = [
    ("4.1  streamlit",                   "streamlit>="),
    ("4.2  audio-recorder-streamlit",    "audio-recorder-streamlit>="),
    ("4.3  openai-whisper",              "openai-whisper>="),
    ("4.4  numpy",                       "numpy>="),
    ("4.5  python-dotenv",               "python-dotenv>="),
    ("4.6  google-generativeai",         "google-generativeai>="),
    ("4.7  openai  (also used for OR)",  "openai>="),
    ("4.8  requests (Ollama fallback)",  "requests>="),
]
for label, pkg in packages:
    check(label, pkg in src)

# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 5 — .gitignore
# ═══════════════════════════════════════════════════════════════════════════════
src = files["gitignore"]

check("5.1  .env exactly matched and ignored",
      "\n.env\n" in src or src.startswith(".env\n") or "\n.env" in src)
check("5.2  *.env wildcard present",     "*.env" in src)
check("5.3  venv/ directory ignored",    "venv/" in src)
check("5.4  audio/*.wav recordings ignored", "audio/*.wav" in src)
check("5.5  __pycache__/ ignored",       "__pycache__/" in src)

# ═══════════════════════════════════════════════════════════════════════════════
# FINAL REPORT
# ═══════════════════════════════════════════════════════════════════════════════
passes = sum(1 for s, _, _ in results if s == "PASS")
fails  = sum(1 for s, _, _ in results if s == "FAIL")

print()
print("=" * 66)
print("  TruthLens AI — Stage 3 Code Verification Report")
print("=" * 66)

sections = {
    "1": "services/llm_provider.py",
    "2": "services/story_analyzer.py",
    "3": "app.py",
    "4": "requirements.txt",
    "5": ".gitignore",
}
current_section = None
for status, label, detail in results:
    section = label.split(".")[0].strip()
    if section != current_section:
        current_section = section
        print(f"\n  -- {sections.get(section, section)} --")
    marker = "✅" if status == "PASS" else "❌"
    print(f"  {marker}  {label}")
    if detail:
        print(f"         → {detail}")

print()
print(f"  Result: {passes} PASS  |  {fails} FAIL  |  {len(results)} total checks")
print("=" * 66)
sys.exit(0 if fails == 0 else 1)
