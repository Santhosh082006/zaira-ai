"""
scratch/run_full_acceptance_verification.py
─────────────────────────────────────────────────────────────────────────────
Full Acceptance Verification Script:
Runs real multimodal extraction, deterministic scoring, cross-comparison,
and PDF generation on real repository media files.
"""

import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from processors.ingestion.video_demuxer import demux_video_to_audio
from processors.context_engine.weighting import get_context_profile, CONTEXT_JOB_INTERVIEW, CONTEXT_VC_PITCH
from services.speech_features import extract_speech_features
from services.visual_features import extract_visual_features
from analytical_engine.evaluator import compute_deterministic_scores
from analytical_engine.cross_comparator import compare_multimodal_performance
from services.report_generator import generate_performance_report, generate_evidence_report

print("=" * 60)
print("TRUTHLENS AI — END-TO-END ACCEPTANCE VERIFICATION")
print("=" * 60)

video_a = os.path.join(ROOT_DIR, "video", "test_video_a.mp4")
video_b = os.path.join(ROOT_DIR, "video", "test_video_b.mp4")

assert os.path.exists(video_a), f"Missing {video_a}"
assert os.path.exists(video_b), f"Missing {video_b}"

# 1. Demux audio
wav_a = os.path.join(ROOT_DIR, "audio", "acceptance_a.wav")
wav_b = os.path.join(ROOT_DIR, "audio", "acceptance_b.wav")

ok_a, err_a = demux_video_to_audio(video_a, wav_a)
ok_b, err_b = demux_video_to_audio(video_b, wav_b)
print(f"1. Demux Video A: {ok_a} | Video B: {ok_b}")

# 2. Extract visual features (MediaPipe)
print("2. Extracting visual features from real video frames...")
vis_a = extract_visual_features(video_a)
vis_b = extract_visual_features(video_b)
print(f"   Video A Visuals: Face={vis_a.get('face_detected')}, HM Count={vis_a.get('head_movement_count')}, HM Rate={vis_a.get('head_movement_rate_per_min')}/min, Presence={vis_a.get('face_presence_ratio'):.0%}")
print(f"   Video B Visuals: Face={vis_b.get('face_detected')}, HM Count={vis_b.get('head_movement_count')}, HM Rate={vis_b.get('head_movement_rate_per_min')}/min, Presence={vis_b.get('face_presence_ratio'):.0%}")

# 3. Extract speech features
print("3. Extracting vocal speech features from extracted audio...")
speech_a = extract_speech_features(wav_a, "I had class at the university in the afternoon then went to the library.") if ok_a else None
speech_b = extract_speech_features(wav_b, "I was studying at the library all afternoon and saw him there.") if ok_b else None
if speech_a:
    print(f"   Video A Speech: Dur={speech_a.get('duration_seconds'):.1f}s, WPM={speech_a.get('speaking_rate_wpm'):.0f}, Pauses={speech_a.get('pause_count')}")
if speech_b:
    print(f"   Video B Speech: Dur={speech_b.get('duration_seconds'):.1f}s, WPM={speech_b.get('speaking_rate_wpm'):.0f}, Pauses={speech_b.get('pause_count')}")

# 4. Deterministic Context Evaluation (Job Interview profile)
print("4. Computing deterministic scores under Job Interview criteria...")
prof_job = get_context_profile(CONTEXT_JOB_INTERVIEW)
eval_a = compute_deterministic_scores("Video A Performer", "I had class at university.", None, speech_a, vis_a, prof_job)
eval_b = compute_deterministic_scores("Video B Performer", "I was studying at library.", None, speech_b, vis_b, prof_job)

print("   Video A Scores:")
for cat, d in eval_a.items():
    print(f"     - {cat:22s}: {d.get('score')}")
print("   Video B Scores:")
for cat, d in eval_b.items():
    print(f"     - {cat:22s}: {d.get('score')}")

# 5. Cross-comparison
print("5. Running Cross-Comparator Engine...")
comp = compare_multimodal_performance(
    eval_a=eval_a,
    eval_b=eval_b,
    speech_a=speech_a,
    speech_b=speech_b,
    visual_a=vis_a,
    visual_b=vis_b,
    profile_key=CONTEXT_JOB_INTERVIEW,
    label_a="Video A",
    label_b="Video B"
)

print(f"   Outcome: {comp.get('outcome_badge')}")
print(f"   Explanation: {comp.get('explanation')}")
print("   Metric Deltas:")
for md in comp.get("metric_deltas", []):
    print(f"     - {md['metric']}: A={md['val_a']} | B={md['val_b']} (Delta: {md['delta']})")

# 6. PDF Reports Generation
print("6. Verifying PDF report generation...")
pdf_perf = generate_performance_report("Video A Performer", None, speech_a, vis_a, eval_a, 85, ["Speech Analysis ✅ Complete", "Visual Analysis ✅ Complete"])
pdf_comp = generate_evidence_report(comp.get("story_comparison") or {}, None, None, speech_a, speech_b, vis_a, vis_b, multimodal_comparison=comp)
assert len(pdf_perf) > 1000, "Performance PDF is too small"
assert len(pdf_comp) > 1000, "Comparison PDF is too small"
print(f"   ✓ Performance Report PDF generated: {len(pdf_perf)} bytes")
print(f"   ✓ Comparison Report PDF generated: {len(pdf_comp)} bytes")

print("=" * 60)
print("ALL ACCEPTANCE VERIFICATION CHECKS PASSED SUCCESSFULLY!")
print("=" * 60)
