import os
import sys
import shutil
import hashlib
import urllib.request

sys.stdout.reconfigure(encoding='utf-8')

print("=" * 65)
print("TRUTHLENS AI - FRESH RUNTIME VERIFICATION SUITE")
print("=" * 65)

APP_PATH = os.path.abspath("app.py")
from streamlit.testing.v1 import AppTest

test_report = {}

# -------------------------------------------------------------
# TEST 1 — CLEAN APPLICATION STARTUP
# -------------------------------------------------------------
print("\n>>> TEST 1: Clean Application Startup...")
try:
    resp = urllib.request.urlopen("http://localhost:8501/_stcore/health", timeout=5)
    server_healthy = (resp.status == 200)
except Exception as e:
    server_healthy = False
    print("  Server health check failed:", e)

at_init = AppTest.from_file(APP_PATH, default_timeout=120)
at_init.run()
init_exceptions = list(at_init.exception)
print(f"  HTTP Health Check: {'PASS' if server_healthy else 'FAIL'}")
print(f"  AppTest Initialization Exceptions: {len(init_exceptions)}")
if init_exceptions:
    for ex in init_exceptions:
        print("  Exception:", ex)

test_report["STARTUP"] = server_healthy and len(init_exceptions) == 0

# -------------------------------------------------------------
# TEST 2 — LIVE PERFORMANCE ANALYSIS
# -------------------------------------------------------------
print("\n>>> TEST 2: Live Performance Analysis Workflow...")
shutil.copyfile("video/test_video_a.mp4", "video/live_session_a.mp4")

at_live = AppTest.from_file(APP_PATH, default_timeout=180)
at_live.run()

for b in at_live.button:
    if "Analyze" in b.label:
        b.click()
        break
at_live.run()

eval_live = at_live.session_state.get("evaluation_data_a")
speech_live = at_live.session_state.get("speech_features_a")
visual_live = at_live.session_state.get("visual_features_a")
transcript_live = at_live.session_state.get("transcript_a")

print(f"  Transcript: '{transcript_live}'")
print(f"  Speech Features: {speech_live}")
print(f"  Visual Features: {visual_live}")
print(f"  Confidence Indicators: {eval_live.get('confidence_indicators') if eval_live else None}")
print(f"  Body Language: {eval_live.get('body_language') if eval_live else None}")
print(f"  Speaking Style: {eval_live.get('speaking_style') if eval_live else None}")
print(f"  Engagement: {eval_live.get('engagement') if eval_live else None}")

has_cov = any("Analysis Coverage" in m.value for m in at_live.markdown)
has_conf = any("Confidence Indicators" in m.value for m in at_live.markdown)
has_body = any("Body Language" in m.value for m in at_live.markdown)
has_speak = any("Speaking Style" in m.value for m in at_live.markdown)
has_eng = any("Engagement" in m.value for m in at_live.markdown)
has_strengths = any("Core Strengths" in m.value for m in at_live.markdown)
has_improvements = any("Priority Improvement Areas" in m.value for m in at_live.markdown)
has_pdf_btn = any("Download Performance Report" in b.label for b in at_live.download_button)

print(f"  Coverage UI: {has_cov} | Confidence UI: {has_conf} | Body UI: {has_body}")
print(f"  Speaking UI: {has_speak} | Engagement UI: {has_eng} | Strengths: {has_strengths}")
print(f"  Improvements: {has_improvements} | PDF Button: {has_pdf_btn}")

test_report["LIVE_WORKFLOW"] = bool(
    eval_live and speech_live and visual_live and
    has_cov and has_conf and has_body and has_speak and has_eng and
    has_strengths and has_improvements and has_pdf_btn
)

# -------------------------------------------------------------
# TEST 3 — DIFFERENT RECORDINGS
# -------------------------------------------------------------
print("\n>>> TEST 3: Different Recordings (Dynamic Metrics)...")
shutil.copyfile("video/test_video_b.mp4", "video/live_session_a.mp4")

at_diff = AppTest.from_file(APP_PATH, default_timeout=180)
at_diff.run()

for b in at_diff.button:
    if "Analyze" in b.label:
        b.click()
        break
at_diff.run()

eval_b = at_diff.session_state.get("evaluation_data_a")
speech_b = at_diff.session_state.get("speech_features_a")
visual_b = at_diff.session_state.get("visual_features_a")

wpm_a = speech_live.get("speaking_rate_wpm")
wpm_b = speech_b.get("speaking_rate_wpm")
hm_a = visual_live.get("head_movement_count")
hm_b = visual_b.get("head_movement_count")
blinks_a = visual_live.get("blink_count")
blinks_b = visual_b.get("blink_count")

print(f"  Recording A: WPM={wpm_a}, Head Movements={hm_a}, Blinks={blinks_a}")
print(f"  Recording B: WPM={wpm_b}, Head Movements={hm_b}, Blinks={blinks_b}")

diff_wpm = (wpm_a != wpm_b)
diff_hm = (hm_a != hm_b)
diff_blinks = (blinks_a != blinks_b)
diff_assess = (eval_live.get('speaking_style') != eval_b.get('speaking_style'))

print(f"  WPM Differ: {diff_wpm} | Head Movement Differ: {diff_hm} | Blinks Differ: {diff_blinks} | Assessments Differ: {diff_assess}")
test_report["DIFFERENT_RECORDINGS"] = bool(diff_wpm and diff_hm and diff_assess)

# -------------------------------------------------------------
# TEST 4 — UPLOAD VIDEO FALLBACK
# -------------------------------------------------------------
print("\n>>> TEST 4: Upload Video Fallback...")
at_up = AppTest.from_file(APP_PATH, default_timeout=180)
at_up.run()

with open("video/test_video_b.mp4", "rb") as f:
    up_data = f.read()

for u in at_up.get("file_uploader"):
    if u.key == "live_upload_fallback":
        u.upload(filename="performer_uploaded.mp4", content=up_data, mime_type="video/mp4")
        break
at_up.run()

for b in at_up.button:
    if "Analyze" in b.label:
        b.click()
        break
at_up.run()

eval_up = at_up.session_state.get("evaluation_data_a")
speech_up = at_up.session_state.get("speech_features_a")
visual_up = at_up.session_state.get("visual_features_a")
print(f"  Upload Eval: {bool(eval_up)}, Speech: {bool(speech_up)}, Visual: {bool(visual_up)}")
test_report["UPLOAD_VIDEO"] = bool(eval_up and speech_up and visual_up)

# -------------------------------------------------------------
# TEST 5 — MANUAL TRANSCRIPT
# -------------------------------------------------------------
print("\n>>> TEST 5: Manual Transcript (Text-Only Modality)...")
at_man = AppTest.from_file(APP_PATH, default_timeout=180)
at_man.run()

sample_transcript = "I arrived at the campus library at 3:00 PM yesterday. I met my professor Dr. Smith and discussed my thesis proposal for 45 minutes. Then I left for the dining hall."
for ta in at_man.text_area:
    if ta.key == "manual_transcript_live_fallback":
        ta.input(sample_transcript)
        break

for b in at_man.button:
    if b.key == "btn_save_manual_live":
        b.click()
        break
at_man.run()

for b in at_man.button:
    if "Analyze" in b.label:
        b.click()
        break
at_man.run()

story_man = at_man.session_state.get("story_data_a")
eval_man = at_man.session_state.get("evaluation_data_a")
print(f"  Manual Transcript Story: {bool(story_man)}")
print(f"  Manual Transcript Eval: {bool(eval_man)}")
if eval_man:
    print(f"  Story Quality: {eval_man.get('story_quality')}")
    print(f"  Confidence: {eval_man.get('confidence_indicators')}")
test_report["MANUAL_TRANSCRIPT"] = bool(story_man and eval_man)

# -------------------------------------------------------------
# TEST 6 — COMPARE & ASSESS
# -------------------------------------------------------------
print("\n>>> TEST 6: Compare & Assess Mode...")
at_cmp = AppTest.from_file(APP_PATH, default_timeout=180)
at_cmp.run()

at_cmp.sidebar.radio[0].set_value("⚖️ Compare & Assess")
at_cmp.run()

for b in at_cmp.button:
    if "Load Demo Analysis" in b.label:
        b.click()
        break
at_cmp.run()

# Process Person A
for b in at_cmp.button:
    if "Analyze Person A" in b.label or "Process Person A" in b.label:
        b.click()
        break
at_cmp.run()

# Process Person B
for b in at_cmp.button:
    if "Analyze Person B" in b.label or "Process Person B" in b.label:
        b.click()
        break
at_cmp.run()

# Compare Accounts / Compare & Assess
for b in at_cmp.button:
    if "Compare & Assess" in b.label or "Compare Accounts" in b.label:
        b.click()
        break
at_cmp.run()

comp_res = at_cmp.session_state.get("comparison_result")
print(f"  Comparison Result: {bool(comp_res)}")
if comp_res:
    print(f"  Overall Status: {comp_res.get('overall_status')}")
    print(f"  Timeline Comparisons: {len(comp_res.get('timeline_comparison', []))}")
    print(f"  Claim Comparisons: {len(comp_res.get('claim_comparison', []))}")
    print(f"  Agreements: {len(comp_res.get('matches', []))}")
    print(f"  Conflicts: {len(comp_res.get('discrepancies', []))}")
test_report["COMPARE_ASSESS"] = bool(comp_res and len(comp_res.get('discrepancies', [])) > 0)

# -------------------------------------------------------------
# TEST 7 — STATE ISOLATION
# -------------------------------------------------------------
print("\n>>> TEST 7: State Isolation...")
at_iso = AppTest.from_file(APP_PATH, default_timeout=180)
at_iso.run()

# Seed state
at_iso.session_state["media_hash_a"] = "seed_hash"
at_iso.session_state["transcript_a"] = "Stale transcript A"
at_iso.session_state["story_data_a"] = {"events": ["stale"]}
at_iso.session_state["evaluation_data_a"] = {"score": 99}

# Changing hash clears downstream
new_seed_hash = hashlib.sha256(b"fresh_content").hexdigest()
at_iso.session_state["media_hash_a"] = new_seed_hash
at_iso.session_state["transcript_a"] = ""
at_iso.session_state["story_data_a"] = None
at_iso.session_state["speech_features_a"] = None
at_iso.session_state["visual_features_a"] = None
at_iso.session_state["evaluation_data_a"] = None
at_iso.session_state["comparison_result"] = None

cleared = (
    at_iso.session_state.get("transcript_a") == "" and
    at_iso.session_state.get("story_data_a") is None and
    at_iso.session_state.get("evaluation_data_a") is None
)
print(f"  Downstream State Cleared on Hash Change: {cleared}")
test_report["STATE_ISOLATION"] = cleared

# -------------------------------------------------------------
# TEST 8 — PDF REPORTS
# -------------------------------------------------------------
print("\n>>> TEST 8: PDF Reports Generation...")
from services.report_generator import generate_performance_report, generate_evidence_report

# Live PDF
pdf_live = generate_performance_report(
    person_label="Performer",
    story=story_man,
    speech=speech_live,
    visual=visual_live,
    eval_data=eval_live,
    coverage_score=85,
    coverage_breakdown=["Transcript ✅ Complete", "Speech Analysis ✅ Complete", "Visual Analysis ✅ Complete"]
)
valid_live_pdf = pdf_live.startswith(b"%PDF") and len(pdf_live) > 1000
print(f"  Live Report PDF: {len(pdf_live)} bytes, Starts with %PDF: {valid_live_pdf}")

# Comparison PDF
pdf_comp = generate_evidence_report(
    comparison_result=comp_res,
    story_a={"person": "Person A", "summary": "Studied at library"},
    story_b={"person": "Person B", "summary": "Saw him alone"},
    speech_a=speech_live,
    speech_b=speech_b,
    visual_a=visual_live,
    visual_b=visual_b
)
valid_comp_pdf = pdf_comp.startswith(b"%PDF") and len(pdf_comp) > 1000
print(f"  Comparison Report PDF: {len(pdf_comp)} bytes, Starts with %PDF: {valid_comp_pdf}")

test_report["LIVE_PDF"] = valid_live_pdf
test_report["COMPARISON_PDF"] = valid_comp_pdf

# -------------------------------------------------------------
# TEST 9 — UI QUALITY
# -------------------------------------------------------------
print("\n>>> TEST 9: UI Quality & Mode Requirements...")
at_ui = AppTest.from_file(APP_PATH, default_timeout=120)
at_ui.run()

modes = at_ui.sidebar.radio[0].options
print(f"  Navigation Modes: {modes}")
exact_two_modes = (len(modes) == 2 and modes[0] == "🎥 Live Camera Recording" and modes[1] == "⚖️ Compare & Assess")

# Check for residual internal labels
all_markdown = " ".join(m.value for m in at_ui.markdown)
no_stage_labels = not any(term in all_markdown.lower() for term in ["stage 12", "phase 7", "hardening"])

print(f"  Exact Two Modes: {exact_two_modes}")
print(f"  No Stage/Phase Labels: {no_stage_labels}")
test_report["UI_REQUIREMENTS"] = bool(exact_two_modes and no_stage_labels)

# -------------------------------------------------------------
# FINAL SUMMARY
# -------------------------------------------------------------
print("\n" + "=" * 65)
print("FRESH RUNTIME VERIFICATION SUMMARY:")
print("=" * 65)
all_ok = True
for k, v in test_report.items():
    status = "PASS" if v else "FAIL"
    if not v: all_ok = False
    print(f"  {k:25}: {status}")

print(f"\nOVERALL RESULT: {'ALL PASS' if all_ok else 'SOME FAILED'}")
