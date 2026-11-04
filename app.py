"""
TruthLens AI — Multimodal Communication & Performance Analysis Platform.

Features:
  1. 🎥 Live Camera — Record live speech and receive evidence-backed performance analysis.
  2. 📁 Upload Video — Upload pre-recorded video evaluated through the identical analysis engine.
  3. ⚖️ Compare Videos — Analyze two recordings independently and compare measured metrics side-by-side.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import uuid
from typing import Optional, Dict, Any, List

import streamlit as st
from dotenv import load_dotenv

from core.constants import (
    AUDIO_DIR,
    VIDEO_DIR,
    CONTEXT_JOB_INTERVIEW,
    CONTEXT_VC_PITCH,
    CONTEXT_CASUAL_MEETING,
    CONTEXT_DISPLAY_NAMES,
    CAT_SPEAKING_STYLE,
    CAT_BODY_LANGUAGE,
    CAT_ENGAGEMENT,
    CAT_CONFIDENCE,
    CAT_STORY_QUALITY,
    ALL_CATEGORIES,
    INSUFFICIENT_DATA,
    FEATURE_LIVE_CAMERA,
    FEATURE_INDIVIDUAL_VIDEO,
    FEATURE_COMPARE_ASSESS,
    ALL_FEATURES,
    DEFAULT_FEATURE,
)
from processors.context_engine.weighting import get_context_profile, PROFILES
from processors.ingestion.video_demuxer import demux_video_to_audio
import importlib
import analytical_engine.evaluator
if not hasattr(analytical_engine.evaluator, "calculate_overall_communication_score"):
    importlib.reload(analytical_engine.evaluator)

from analytical_engine.evaluator import (
    evaluate_account_with_explanation,
    calculate_overall_communication_score,
)
from analytical_engine.cross_comparator import compare_multimodal_performance
from services.speech_to_text import load_whisper_model, transcribe_audio
from services.story_analyzer import extract_story_facts, validate_extracted_story, evaluate_individual_account
from services.speech_features import extract_speech_features
from services.visual_features import extract_visual_features
from services.report_generator import generate_performance_report, generate_evidence_report
import ui.theme
if not hasattr(ui.theme, "top_navigation_bar_html"):
    importlib.reload(ui.theme)

from ui.theme import (
    FONT_IMPORT,
    PREMIUM_CSS,
    top_navigation_bar_html,
    editorial_page_header_html,
    cinematic_hud_stage_overlay,
    studio_guidelines_strip_html,
    hero_score_radial_gauge_html,
    category_card_luxury_html,
    comparison_verdict_hero_html,
    comparison_vs_nexus_html,
    recording_live_pulse_html,
    section_divider_glow_html,
    section_label_chip_html,
    coverage_bar_html,
    page_header_html,
    recording_indicator_html,
    winner_badge_html,
    recommendation_html,
    evidence_badge_html,
    section_label_html,
    separator_html,
)

# ── Load environment variables ─────────────────────────────────────────────────
load_dotenv()
os.makedirs(AUDIO_DIR, exist_ok=True)
os.makedirs(VIDEO_DIR, exist_ok=True)

# ── Page configuration ─────────────────────────────────────────────────────────
st.set_page_config(
    page_title="TruthLens AI",
    page_icon="🔍",
    layout="wide",
)

# ── Inject Premium Design System ───────────────────────────────────────────────
st.markdown(FONT_IMPORT, unsafe_allow_html=True)
st.markdown(PREMIUM_CSS, unsafe_allow_html=True)

# ── Cache the Whisper model ────────────────────────────────────────────────────
@st.cache_resource(
    show_spinner="Loading Whisper model — this may take a moment on first run…"
)
def get_whisper_model():
    return load_whisper_model("base")


# ═══════════════════════════════════════════════════════════════════════════════
# STATE MANAGEMENT & ISOLATION HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def init_session_lifecycle() -> str:
    """
    Initialize clean session state for a new browser session without affecting normal reruns.
    Ensures that a new session starts with no stale recordings, inputs, or analyses.
    """
    if "_session_id" not in st.session_state:
        session_id = uuid.uuid4().hex[:12]
        st.session_state["_session_id"] = session_id
        st.session_state["active_feature"] = DEFAULT_FEATURE
        st.session_state["sidebar_primary_nav"] = DEFAULT_FEATURE
        for pid in ["live", "upload", "a", "b"]:
            st.session_state[f"video_path_{pid}"] = None
            st.session_state[f"media_hash_{pid}"] = None
            st.session_state[f"live_mtime_{pid}"] = 0.0
            reset_person_downstream(pid)
        st.session_state["comparison_result"] = None
        st.session_state["multimodal_comparison"] = None
        st.session_state["_live_was_recording"] = False
        st.session_state["live_recorded_this_session"] = False
    return st.session_state["_session_id"]


def reset_person_downstream(person_id: str) -> None:
    """Invalidate all downstream analysis artifacts for a specific person/slot."""
    st.session_state[f"transcript_{person_id}"] = ""
    st.session_state[f"textarea_{person_id}"] = ""
    st.session_state[f"_sync_transcript_{person_id}"] = True
    st.session_state[f"audio_path_{person_id}"] = None
    st.session_state[f"audio_bytes_{person_id}"] = None
    st.session_state[f"speech_features_{person_id}"] = None
    st.session_state[f"visual_features_{person_id}"] = None
    st.session_state[f"story_data_{person_id}"] = None
    st.session_state[f"evaluation_data_{person_id}"] = None
    st.session_state["comparison_result"] = None
    st.session_state["multimodal_comparison"] = None


# ═══════════════════════════════════════════════════════════════════════════════
# OBSERVATION & COVERAGE METRICS
# ═══════════════════════════════════════════════════════════════════════════════

def get_speech_observations(feats: Optional[Dict[str, Any]]) -> List[str]:
    """Generate human-readable observations from measured acoustic signals."""
    if not feats or feats.get("duration_seconds") is None or feats.get("reliability_flag") != "good":
        return ["Speech audio unmeasured or acoustic features unavailable for this recording."]
    obs = []
    wpm = feats.get("speaking_rate_wpm")
    if wpm is not None:
        obs.append(f"The measured speaking rate was {wpm:.0f} WPM.")

    fillers = feats.get("filler_word_count")
    if fillers is not None:
        if fillers == 0:
            obs.append("Very few filler words were detected.")
        elif fillers <= 2:
            obs.append(f"Few filler words were detected ({fillers} instances).")
        else:
            obs.append(f"Noticeable filler words detected ({fillers} instances).")

    pauses = feats.get("pause_count")
    p_dur = feats.get("total_pause_duration_sec")
    if pauses is not None:
        if pauses == 0:
            obs.append("No long pauses were detected.")
        elif pauses > 2 and p_dur is not None:
            obs.append(f"Longer pauses detected between statements ({pauses} pauses, {p_dur:.1f}s total).")
        else:
            obs.append(f"Longer pauses detected between statements ({pauses} pauses).")

    if not obs:
        obs.append("Acoustic features were extracted but no distinct anomalies were flagged.")
    return obs


def get_visual_observations(v_feats: Optional[Dict[str, Any]]) -> List[str]:
    """Generate human-readable observations from measured visual tracking."""
    if not v_feats or not v_feats.get("face_detected") or v_feats.get("tracking_reliability") != "good":
        return ["Visual tracking did not detect a face or tracking was unavailable."]
    obs = ["Face visibility was consistent during the analyzed portion of the recording."]

    hm = v_feats.get("head_movement_count")
    hm_rate = v_feats.get("head_movement_rate_per_min")
    if hm_rate is not None:
        if hm_rate > 35:
            obs.append(f"Frequent head movement was observed at {hm_rate:.1f} movements/min, above the configured 15-35/min reference range.")
        elif hm_rate < 10:
            obs.append(f"Minimal head movement was observed at {hm_rate:.1f} movements/min, below configured 15-35/min reference range.")
        else:
            obs.append(f"Head movement was measured at {hm_rate:.1f} movements/min, within configured 15-35/min reference range.")
    elif hm is not None:
        if hm > 15:
            obs.append(f"Head movement shifts observed: {hm}.")
        else:
            obs.append("Head position remained relatively stable.")

    return obs


def calculate_analysis_coverage(person_id: str) -> tuple[int, List[str]]:
    """
    Calculate data completeness coverage score (0-100) and breakdown checklist.
    Guarantees no false 100% scores when audio or visual modalities are missing.
    """
    transcript = (st.session_state.get(f"transcript_{person_id}") or "").strip()
    has_text = bool(transcript)
    has_audio = bool(st.session_state.get(f"audio_path_{person_id}"))
    has_video = bool(st.session_state.get(f"video_path_{person_id}"))

    speech_feats = st.session_state.get(f"speech_features_{person_id}")
    valid_speech = bool(
        speech_feats
        and speech_feats.get("duration_seconds") is not None
        and speech_feats.get("duration_seconds") > 0
        and speech_feats.get("speaking_rate_wpm") is not None
        and speech_feats.get("reliability_flag") == "good"
    )

    visual_feats = st.session_state.get(f"visual_features_{person_id}")
    valid_visual = bool(
        visual_feats
        and visual_feats.get("face_detected") is True
        and visual_feats.get("tracking_reliability") == "good"
    )

    story_data = st.session_state.get(f"story_data_{person_id}")
    valid_story = bool(story_data and (story_data.get("events") or story_data.get("claims")))

    eval_data = st.session_state.get(f"evaluation_data_{person_id}")

    breakdown = []
    total_checks = 0
    passed_checks = 0.0

    # 1. Input Data
    total_checks += 1
    if has_audio or has_video or has_text:
        breakdown.append("Input Data&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;✅ Available")
        passed_checks += 1
    else:
        breakdown.append("Input Data&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;❌ Unavailable")

    # 2. Transcript
    total_checks += 1
    if has_text and len(transcript.split()) >= 6:
        breakdown.append("Transcript&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;✅ Complete")
        passed_checks += 1
    elif has_text:
        breakdown.append("Transcript&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;⚠️ Minimal (<6 words)")
        passed_checks += 0.5
    else:
        breakdown.append("Transcript&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;❌ Unavailable")

    # 3. Speech Analysis
    if has_audio or has_video:
        total_checks += 1
        if valid_speech:
            breakdown.append("Speech Analysis&nbsp;✅ Complete")
            passed_checks += 1
        elif speech_feats and speech_feats.get("duration_seconds") is None:
            breakdown.append("Speech Analysis&nbsp;❌ Failed/Unmeasured (No Audio Signal)")
        else:
            breakdown.append("Speech Analysis&nbsp;❌ Failed/Unavailable")

    # 4. Visual Analysis
    if has_video:
        total_checks += 1
        if valid_visual:
            breakdown.append("Visual Analysis&nbsp;✅ Complete")
            passed_checks += 1
        elif visual_feats and visual_feats.get("face_presence_ratio", 0) > 0:
            breakdown.append("Visual Analysis&nbsp;⚠️ Partial (Intermittent Tracking)")
            passed_checks += 0.5
        else:
            breakdown.append("Visual Analysis&nbsp;❌ Failed/No Face Detected")

    # 5. Story Analysis
    total_checks += 1
    if valid_story:
        breakdown.append("Story Analysis&nbsp;&nbsp;✅ Complete")
        passed_checks += 1
    elif has_text:
        breakdown.append("Story Analysis&nbsp;&nbsp;⚠️ Partial Extraction")
        passed_checks += 0.5
    else:
        breakdown.append("Story Analysis&nbsp;&nbsp;❌ Unavailable")

    # 6. Performance Evaluation
    total_checks += 1
    if eval_data and isinstance(eval_data, dict):
        scored_dims = sum(
            1 for item in eval_data.values()
            if isinstance(item, dict) and isinstance(item.get("score"), int)
        )
        if scored_dims >= 4:
            breakdown.append("Individual Eval&nbsp;✅ Complete")
            passed_checks += 1
        elif scored_dims > 0:
            breakdown.append(f"Individual Eval&nbsp;⚠️ Partial ({scored_dims}/5 Categories Scored)")
            passed_checks += round(scored_dims / 5.0, 2)
        else:
            breakdown.append("Individual Eval&nbsp;⚠️ Insufficient Data (0 Categories Scored)")
            passed_checks += 0.1
    else:
        breakdown.append("Individual Eval&nbsp;❌ Unavailable")

    score = int(round((passed_checks / max(1, total_checks)) * 100))
    return score, breakdown


# ═══════════════════════════════════════════════════════════════════════════════
# COMMON VIDEO ANALYSIS PIPELINE (SHARED BY ALL FEATURES)
# ═══════════════════════════════════════════════════════════════════════════════

def run_pipeline(
    person_id: str,
    person_label: str,
    context_key: str = "job_interview"
) -> bool:
    """
    Unified multimodal analysis pipeline.
    Shared identically by Live Camera, Upload Video, and Compare Videos.
    1. Demux video -> Audio WAV
    2. Transcribe audio (Whisper with cloud fallback)
    3. Acoustic speech features extraction (DSP)
    4. Visual face & movement tracking (MediaPipe)
    5. Story structure extraction
    6. Context-aware deterministic performance scoring + qualitative explanation
    """
    video_path_key      = f"video_path_{person_id}"
    audio_path_key      = f"audio_path_{person_id}"
    audio_key           = f"audio_bytes_{person_id}"
    transcript_key      = f"transcript_{person_id}"
    speech_features_key = f"speech_features_{person_id}"
    visual_features_key = f"visual_features_{person_id}"
    story_key           = f"story_data_{person_id}"
    eval_key            = f"evaluation_data_{person_id}"

    with st.status(f"🔄 Analyzing {person_label}...", expanded=True) as status:
        try:
            # 1. Video -> Audio extraction
            if st.session_state.get(video_path_key) and not st.session_state.get(audio_path_key):
                st.write("⏳ Extracting audio track...")
                extracted_path = os.path.join(AUDIO_DIR, f"session_{person_id}_extracted.wav")
                success, err = demux_video_to_audio(st.session_state[video_path_key], extracted_path)
                if success:
                    st.session_state[audio_path_key] = extracted_path
                    with open(extracted_path, "rb") as f:
                        st.session_state[audio_key] = f.read()
                    st.write("✓ Audio extracted")
                else:
                    st.write(f"⚠️ Audio track could not be separated: {err}")

            # 2. Transcription
            if st.session_state.get(audio_path_key) and not (st.session_state.get(transcript_key) or "").strip():
                st.write("⏳ Transcribing speech...")
                trans_success = False

                # Local Whisper attempt
                try:
                    model = get_whisper_model()
                    text = transcribe_audio(model, st.session_state[audio_path_key])
                    st.session_state[transcript_key] = text
                    st.session_state[f"_sync_transcript_{person_id}"] = True
                    st.write("✓ Speech transcribed (Local Whisper)")
                    trans_success = True
                except Exception as e:
                    st.write(f"⚠️ Local Whisper unavailable ({str(e)})")

                # Cloud fallback attempt if local failed
                if not trans_success:
                    groq_key = os.getenv("GROQ_API_KEY")
                    openai_key = os.getenv("OPENAI_API_KEY")
                    if groq_key:
                        try:
                            from groq import Groq
                            client = Groq(api_key=groq_key)
                            with open(st.session_state[audio_path_key], "rb") as file:
                                transcription = client.audio.transcriptions.create(
                                    file=(st.session_state[audio_path_key], file.read()),
                                    model="whisper-large-v3-turbo"
                                )
                            st.session_state[transcript_key] = transcription.text
                            st.session_state[f"_sync_transcript_{person_id}"] = True
                            st.write("✓ Speech transcribed (Cloud Provider)")
                            trans_success = True
                        except Exception as cloud_e:
                            st.write(f"⚠️ Fallback transcription failed: {cloud_e}")
                    elif openai_key:
                        try:
                            from openai import OpenAI
                            client = OpenAI(api_key=openai_key)
                            with open(st.session_state[audio_path_key], "rb") as audio_file:
                                transcription = client.audio.transcriptions.create(
                                    model="whisper-1", file=audio_file
                                )
                            st.session_state[transcript_key] = transcription.text
                            st.session_state[f"_sync_transcript_{person_id}"] = True
                            st.write("✓ Speech transcribed (Cloud Provider)")
                            trans_success = True
                        except Exception as cloud_e:
                            st.write(f"⚠️ Fallback transcription failed: {cloud_e}")

                if not trans_success:
                    st.session_state[transcript_key] = ""
                    st.session_state[f"_sync_transcript_{person_id}"] = True

            # 3. Speech Acoustic Analysis
            if st.session_state.get(audio_path_key) and not st.session_state.get(speech_features_key):
                st.write("⏳ Analyzing vocal delivery...")
                try:
                    feats = extract_speech_features(
                        st.session_state[audio_path_key],
                        st.session_state.get(transcript_key, "")
                    )
                    st.session_state[speech_features_key] = feats
                    if feats.get("duration_seconds") is not None and feats.get("reliability_flag") == "good":
                        st.write("✓ Vocal signals analyzed")
                    else:
                        st.write("⚠️ Acoustic signals limited or silent")
                except Exception as e:
                    st.write(f"⚠️ Speech analysis unavailable: {e}")

            # 4. Visual Tracking Analysis
            if st.session_state.get(video_path_key) and not st.session_state.get(visual_features_key):
                st.write("⏳ Analyzing visual posture & engagement...")
                try:
                    v_feats = extract_visual_features(st.session_state[video_path_key])
                    st.session_state[visual_features_key] = v_feats
                    if v_feats.get("face_detected") and v_feats.get("tracking_reliability") == "good":
                        st.write("✓ Visual signals analyzed")
                    else:
                        st.write(f"⚠️ Visual tracking limited ({v_feats.get('tracking_reliability', 'unmeasured')})")
                except Exception as e:
                    st.write(f"⚠️ Visual analysis unavailable: {e}")

            # 5. Story Narrative Extraction
            raw_trans = st.session_state.get(transcript_key)
            curr_trans = (raw_trans.get("text", "") if isinstance(raw_trans, dict) else str(raw_trans or "")).strip()
            if curr_trans and len(curr_trans.split()) >= 6 and not st.session_state.get(story_key):
                st.write("⏳ Extracting structured narrative...")
                try:
                    story_data = extract_story_facts(transcript=curr_trans, person_name=person_label)
                    is_valid, errs = validate_extracted_story(story_data)
                    if not is_valid:
                        raise RuntimeError("; ".join(errs))
                    st.session_state[story_key] = story_data
                    st.write("✓ Narrative structure extracted")
                except Exception as e:
                    st.write(f"⚠️ Narrative extraction limited: {e}")

            # 6. Context-Aware Performance Assessment
            st.write("⏳ Computing evidence-backed performance scores...")
            try:
                eval_data = evaluate_account_with_explanation(
                    person_name=person_label,
                    transcript=st.session_state.get(transcript_key, ""),
                    story_data=st.session_state.get(story_key),
                    speech_feats=st.session_state.get(speech_features_key),
                    visual_feats=st.session_state.get(visual_features_key),
                    profile_key=context_key
                )
                st.session_state[eval_key] = eval_data
                st.write("✓ Performance assessment complete")
            except Exception as e:
                st.write(f"⚠️ Assessment error: {e}")

            status.update(label=f"✓ {person_label} Analysis Complete", state="complete", expanded=False)
            return True
        except Exception as e:
            st.error(f"❌ Analysis stopped: {str(e)}")
            status.update(label=f"❌ {person_label} Analysis Failed", state="error", expanded=True)
            return False


# ═══════════════════════════════════════════════════════════════════════════════
# INDIVIDUAL PERFORMANCE REPORT RENDERER
# ═══════════════════════════════════════════════════════════════════════════════

def render_individual_analysis(person_id: str, person_label: str) -> None:
    """Render full performance results, coverage, observations, and PDF download."""
    story = st.session_state.get(f"story_data_{person_id}")
    eval_data = st.session_state.get(f"evaluation_data_{person_id}")
    raw_trans = st.session_state.get(f"transcript_{person_id}")
    transcript = (raw_trans.get("text", "") if isinstance(raw_trans, dict) else str(raw_trans or "")).strip()
    speech_feats = st.session_state.get(f"speech_features_{person_id}")
    visual_feats = st.session_state.get(f"visual_features_{person_id}")
    video_path = st.session_state.get(f"video_path_{person_id}")

    has_any = any([transcript, speech_feats, visual_feats, story, eval_data])
    if not has_any:
        return

    st.markdown("## PERFORMANCE ANALYSIS")
    st.markdown("────────────────────────────")

    assessment_keys = [
        (CAT_SPEAKING_STYLE, "Speaking Style & Fluency"),
        (CAT_STORY_QUALITY, "Narrative Detail"),
        (CAT_ENGAGEMENT, "Camera Presence"),
        (CAT_BODY_LANGUAGE, "Body Language"),
        (CAT_CONFIDENCE, "Delivery Composure")
    ]

    score, breakdown = calculate_analysis_coverage(person_id)

    # 1. PERFORMANCE OVERVIEW
    if eval_data:
        active_context_key = st.session_state.get("_active_context_key", CONTEXT_JOB_INTERVIEW)
        profile = get_context_profile(active_context_key)
        overall_score, overall_assessment = calculate_overall_communication_score(eval_data, profile)

        st.markdown("### PERFORMANCE OVERVIEW")
        score_disp = f"{overall_score} / 100" if isinstance(overall_score, (int, float)) else str(overall_score)
        st.markdown(f"**{score_disp} Overall Performance**")
        st.markdown(f"{overall_assessment}")
        st.markdown("────────────────────────────")

        # 2. KEY SCORES
        st.markdown("### KEY SCORES")
        c1, c2, c3, c4 = st.columns(4)
        cols = [c1, c2, c3, c4]
        
        display_keys = [
            (CAT_SPEAKING_STYLE, "Speaking Style"),
            (CAT_STORY_QUALITY, "Narrative Detail"),
            (CAT_ENGAGEMENT, "Camera Presence"),
            (CAT_BODY_LANGUAGE, "Body Language")
        ]
        
        for idx, (key, title) in enumerate(display_keys):
            v = eval_data.get(key)
            if isinstance(v, dict):
                score_val = v.get("score", INSUFFICIENT_DATA)
                with cols[idx]:
                    st.metric(title, f"{score_val}/100" if isinstance(score_val, (int, float)) else str(score_val))
        
        st.markdown("────────────────────────────")

        # 3. WHAT WENT WELL
        st.markdown("### WHAT WENT WELL")
        strengths_found = False
        for key, title in assessment_keys:
            v = eval_data.get(key)
            if isinstance(v, dict):
                www = v.get("what_went_well")
                if www and str(www).strip().upper() != "N/A":
                    st.markdown(f"- ✅ **{title}**: {www}")
                    strengths_found = True
        if not strengths_found:
            st.caption("No specific strengths measured.")
        
        st.markdown("────────────────────────────")

        # 4. NEEDS IMPROVEMENT
        st.markdown("### NEEDS IMPROVEMENT")
        improvements_found = False
        imp_count = 1
        for key, title in assessment_keys:
            v = eval_data.get(key)
            if isinstance(v, dict):
                wni = v.get("what_needs_improvement")
                if wni and str(wni).strip().upper() != "N/A":
                    st.markdown(f"{imp_count}. **{title}**: {wni}")
                    imp_count += 1
                    improvements_found = True
        if not improvements_found:
            st.caption("No specific improvements flagged.")
            
        st.markdown("────────────────────────────")

        with st.expander("DETAILED ANALYSIS"):
            for key, title in assessment_keys:
                v = eval_data.get(key)
                if isinstance(v, dict):
                    st.markdown(f"**{title}**")
                    st.markdown(v.get('assessment', ''))

        st.markdown("────────────────────────────")

    # EVIDENCE
    with st.expander("EVIDENCE"):
        st.markdown("**Speech Observations**")
        obs = get_speech_observations(speech_feats)
        for o in obs:
            st.markdown(f"- {o}")
        if speech_feats and speech_feats.get("duration_seconds") is not None:
            st.caption(f"Duration: {speech_feats.get('duration_seconds', 0):.1f}s | Rate: {speech_feats.get('speaking_rate_wpm', 0):.0f} WPM")
            
        st.markdown("**Visual Observations**")
        if visual_feats:
            obs = get_visual_observations(visual_feats)
            for o in obs:
                st.markdown(f"- {o}")
        else:
            st.markdown("- No video input provided.")

    st.markdown("────────────────────────────")

    # ANALYSIS COVERAGE
    with st.expander("ANALYSIS COVERAGE"):
        st.markdown(f"**Coverage Score: {score}/100**")
        for b in breakdown:
            st.markdown(b, unsafe_allow_html=True)

    st.markdown("────────────────────────────")

    # TRANSCRIPT
    with st.expander("TRANSCRIPT"):
        if transcript:
            st.markdown(f"{transcript}")
        else:
            st.caption("No transcript available.")

    st.markdown("---")
    pdf_bytes = generate_performance_report(
        person_label=person_label,
        story=story,
        speech=speech_feats,
        visual=visual_feats,
        eval_data=eval_data,
        coverage_score=score,
        coverage_breakdown=breakdown
    )
    st.download_button(
        "📄 Download Report (PDF)",
        data=pdf_bytes,
        file_name=f"TruthLens_Report_{person_id}.pdf",
        mime="application/pdf",
        type="primary",
        use_container_width=True,
        key=f"dl_pdf_{person_id}"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# COMPARISON DISPLAY RENDERER
# ═══════════════════════════════════════════════════════════════════════════════

def render_comparison_view(comp: Dict[str, Any], label_a: str = "Video A", label_b: str = "Video B") -> None:
    """Render side-by-side comparative analysis, metric deltas, and mathematical winner."""
    st.markdown(section_divider_glow_html(), unsafe_allow_html=True)

    outcome = comp.get("outcome_badge", "Comparable Result")
    explanation = comp.get("explanation", "")
    st.markdown(comparison_verdict_hero_html(outcome, explanation), unsafe_allow_html=True)

    metric_deltas = comp.get("metric_deltas", [])
    if metric_deltas:
        st.markdown(section_divider_glow_html(), unsafe_allow_html=True)
        st.markdown(section_label_chip_html("Signal Comparison"), unsafe_allow_html=True)
        for m in metric_deltas:
            col_m1, col_m2, col_m3 = st.columns([1, 1, 2])
            with col_m1:
                st.metric(f"{label_a} {m['metric']}", m['val_a'])
            with col_m2:
                st.metric(f"{label_b} {m['metric']}", m['val_b'], delta=m['delta'])
            with col_m3:
                st.markdown(f"<div style='font-size:0.9rem;color:var(--tl-text-secondary);margin-top:0.4rem;'>💡 <strong>Interpretation:</strong> {m['interpretation']}</div>", unsafe_allow_html=True)

    cat_comps = comp.get("category_comparisons", [])
    if cat_comps:
        st.markdown(section_divider_glow_html(), unsafe_allow_html=True)
        st.markdown(section_label_chip_html("Category Scores"), unsafe_allow_html=True)
        cols = st.columns(len(cat_comps))
        for idx, c in enumerate(cat_comps):
            with cols[idx]:
                st.markdown(f"<div style='font-size:0.95rem;font-weight:700;color:var(--tl-text-primary);'>{c['category']}</div>", unsafe_allow_html=True)
                st.markdown(f"<div style='font-size:0.9rem;'>{label_a}: <strong>{c['score_a']}</strong><br>{label_b}: <strong>{c['score_b']}</strong></div>", unsafe_allow_html=True)
                delta_color = "var(--tl-green-primary)" if "+" in str(c['delta']) else "var(--tl-amber-primary)" if "-" in str(c['delta']) else "var(--tl-text-muted)"
                st.markdown(f"<div style='font-size:0.85rem;color:{delta_color};font-weight:600;'>Delta: {c['delta']}</div>", unsafe_allow_html=True)
                st.caption(f"Status: {c['status']}")

    story_comp = comp.get("story_comparison")
    if story_comp and isinstance(story_comp, dict):
        st.markdown(section_divider_glow_html(), unsafe_allow_html=True)
        st.markdown(section_label_chip_html("Narrative Consistency"), unsafe_allow_html=True)
        overall = str(story_comp.get("overall_status", "unclear")).lower()
        if overall == "consistent":
            st.markdown("<p style='color:var(--tl-green-primary);'>🟢 <strong>Consistent</strong> — Both accounts align on chronological events.</p>", unsafe_allow_html=True)
        elif overall == "discrepancies_found":
            st.markdown("<p style='color:var(--tl-amber-primary);'>🔴 <strong>Discrepancies Found</strong> — Divergent accounts or conflicting details detected.</p>", unsafe_allow_html=True)
        else:
            st.markdown(f"<p style='color:var(--tl-text-primary);'>ℹ️ <strong>{overall.replace('_', ' ').title()}</strong></p>", unsafe_allow_html=True)

        summary = story_comp.get("summary")
        if summary:
            st.markdown(f"<div style='font-size:0.9rem;color:var(--tl-text-secondary);'><strong>Summary:</strong> {summary}</div>", unsafe_allow_html=True)

        if story_comp.get("semantic_comparison_available") is False:
            st.caption("ℹ️ Semantic AI Narrative Comparison is currently unavailable (Provider offline or budget exhausted). Displaying rule-based lexical matching.")

    st.markdown(section_divider_glow_html(), unsafe_allow_html=True)
    pdf_bytes = generate_evidence_report(
        comparison_result=story_comp or {},
        story_a=st.session_state.get("story_data_a"),
        story_b=st.session_state.get("story_data_b"),
        speech_a=st.session_state.get("speech_features_a"),
        speech_b=st.session_state.get("speech_features_b"),
        visual_a=st.session_state.get("visual_features_a"),
        visual_b=st.session_state.get("visual_features_b"),
        multimodal_comparison=comp
    )
    st.download_button(
        "📄 Export Comparison Audit Report (PDF)",
        data=pdf_bytes,
        file_name="TruthLens_Comparison_Report.pdf",
        mime="application/pdf",
        type="primary",
        use_container_width=True
    )


# ═══════════════════════════════════════════════════════════════════════════════
# FEATURE 1: 🎥 LIVE CAMERA
# ═══════════════════════════════════════════════════════════════════════════════

def render_feature_live_camera(active_context_key: str) -> None:
    st.markdown(top_navigation_bar_html("Live Studio", CONTEXT_DISPLAY_NAMES.get(active_context_key, "Job Interview")), unsafe_allow_html=True)
    st.markdown(editorial_page_header_html(
        "LIVE PERFORMANCE",
        "Record & Analyze",
        "Capture yourself speaking and receive detailed performance feedback."
    ), unsafe_allow_html=True)

    person_id = "live"
    person_label = "Live Performer"
    video_path_key = f"video_path_{person_id}"
    session_id = st.session_state.get("_session_id", "default")
    live_video_path = os.path.join(VIDEO_DIR, f"live_session_{session_id}.mp4")

    ctx = None
    c_stage, c_guide = st.columns([3, 1])
    with c_stage:
        st.markdown(cinematic_hud_stage_overlay("Camera"), unsafe_allow_html=True)
        try:
            from streamlit_webrtc import webrtc_streamer, WebRtcMode, RTCConfiguration
            from aiortc.contrib.media import MediaRecorder

            def create_recorder():
                return MediaRecorder(live_video_path)

            rtc_config = RTCConfiguration(
                {"iceServers": [{"urls": ["stun:stun.l.google.com:19302"]}]}
            )
            ctx = webrtc_streamer(
                key=f"live_camera_capture_{session_id}",
                mode=WebRtcMode.SENDRECV,
                rtc_configuration=rtc_config,
                in_recorder_factory=create_recorder,
                media_stream_constraints={"video": True, "audio": True},
                video_html_attrs={
                    "style": {"width": "100%", "border-radius": "16px"},
                    "controls": False,
                    "autoPlay": True,
                    "muted": True,
                    "playsInline": True
                }
            )

            if ctx and ctx.state.playing:
                st.session_state["_live_was_recording"] = True
                st.markdown(recording_live_pulse_html(), unsafe_allow_html=True)
        except Exception as e:
            st.warning(f"Live camera recording component: {e}. You can also use pre-recorded samples.")

    with c_guide:
        st.markdown("### Before you begin")
        st.markdown("Ensure your face is well-lit and clearly visible. Speak naturally as you would in a real conversation.<br><span style='color:var(--tl-text-secondary);font-size:0.85rem;'><strong>Note:</strong> Performance metrics (speaking rate, acoustic pauses, posture stability, and narrative structure) are analyzed immediately after you finish recording.</span>", unsafe_allow_html=True)
        
        sample_path = os.path.join(VIDEO_DIR, "test_video_a.mp4")
        if os.path.exists(sample_path):
            with st.expander("⚡ Use Pre-Recorded Sample"):
                if st.button("Load Sample Video", key="btn_use_sample_live", use_container_width=True):
                    shutil.copyfile(sample_path, live_video_path)
                    with open(live_video_path, "rb") as f:
                        curr_hash = hashlib.sha256(f.read()).hexdigest()
                    st.session_state[f"live_mtime_{person_id}"] = os.path.getmtime(live_video_path)
                    st.session_state[f"media_hash_{person_id}"] = curr_hash
                    st.session_state[video_path_key] = live_video_path
                    st.session_state["live_recorded_this_session"] = True
                    reset_person_downstream(person_id)
                    st.success("Sample loaded.")
                    st.rerun()

    if st.session_state.get("_live_was_recording") and (not ctx or not ctx.state.playing):
        st.session_state["_live_was_recording"] = False
        if os.path.exists(live_video_path) and os.path.getsize(live_video_path) > 0:
            with open(live_video_path, "rb") as f:
                curr_hash = hashlib.sha256(f.read()).hexdigest()
            st.session_state[f"media_hash_{person_id}"] = curr_hash
            st.session_state[f"live_mtime_{person_id}"] = os.path.getmtime(live_video_path)
            st.session_state[video_path_key] = live_video_path
            st.session_state["live_recorded_this_session"] = True
            reset_person_downstream(person_id)
            st.rerun()

    if st.session_state.get(video_path_key) and os.path.exists(st.session_state[video_path_key]):
        st.markdown(section_divider_glow_html(), unsafe_allow_html=True)
        st.markdown("### Review & Analyze")
        st.video(st.session_state[video_path_key])
        st.markdown("<div style='margin-bottom:1rem;'></div>", unsafe_allow_html=True)
        if st.button("Analyze Performance", type="primary", use_container_width=True, key="btn_analyze_live"):
            run_pipeline(person_id, person_label, context_key=active_context_key)

        render_individual_analysis(person_id, person_label)

    st.session_state["live_recording"] = st.session_state.get(video_path_key)
    st.session_state["live_video"] = st.session_state.get(video_path_key)
    st.session_state["live_transcript"] = st.session_state.get(f"transcript_{person_id}")
    st.session_state["live_features"] = st.session_state.get(f"speech_features_{person_id}")
    st.session_state["live_analysis"] = st.session_state.get(f"evaluation_data_{person_id}")


# ═══════════════════════════════════════════════════════════════════════════════
# FEATURE 2: 📁 INDIVIDUAL VIDEO ANALYSIS
# ═══════════════════════════════════════════════════════════════════════════════

def render_feature_individual_video(active_context_key: str) -> None:
    st.markdown(top_navigation_bar_html("Video Analysis", CONTEXT_DISPLAY_NAMES.get(active_context_key, "Job Interview")), unsafe_allow_html=True)
    st.markdown(editorial_page_header_html(
        "INDIVIDUAL PERFORMANCE",
        "Analyze Your Video",
        "Upload a recording to get detailed communication performance feedback."
    ), unsafe_allow_html=True)

    person_id = "upload"
    person_label = "Individual Performer"
    video_path_key = f"video_path_{person_id}"
    session_id = st.session_state.get("_session_id", "default")

    if not (st.session_state.get(video_path_key) and os.path.exists(st.session_state[video_path_key])):
        st.write("")
        st.write("")
        st.write("")
        st.markdown("""
        <div style="text-align:center;padding:8rem 0;margin: 2rem 0;background: transparent;">
            <div style="font-size:2.5rem;font-weight:300;color:var(--tl-text-primary);margin-bottom:0.5rem;letter-spacing:-0.02em;">Drop your canvas here</div>
            <div style="font-size:1.2rem;color:var(--tl-text-secondary);margin-bottom:2rem;font-weight:300;">MP4, WEBM, or MOV up to 200MB</div>
        """, unsafe_allow_html=True)
        
        c_ul_left, c_ul_center, c_ul_right = st.columns([1, 2, 1])
        with c_ul_center:
            uploaded_file = st.file_uploader(
                "Drop your recording:",
                type=["mp4", "webm", "mov"],
                key=f"uploader_individual_video_{session_id}",
                label_visibility="hidden"
            )
        st.markdown("</div>", unsafe_allow_html=True)
        st.write("")
        st.write("")
        st.write("")

        if uploaded_file:
            buffer = uploaded_file.getbuffer()
            file_hash = hashlib.sha256(buffer).hexdigest()

            if st.session_state.get(f"media_hash_{person_id}") != file_hash:
                st.session_state[f"media_hash_{person_id}"] = file_hash
                save_path = os.path.join(VIDEO_DIR, f"individual_video_{session_id}.mp4")
                with open(save_path, "wb") as f:
                    f.write(buffer)
                st.session_state[video_path_key] = save_path
                reset_person_downstream(person_id)
                st.rerun()

        sample_files = [f for f in os.listdir(VIDEO_DIR) if f.endswith(".mp4")]
        if sample_files:
            with st.expander("Or use a sample video"):
                chosen = st.selectbox("Choose sample video:", sample_files, key="select_sample_individual")
                if st.button("Load Sample", key="btn_load_sample_individual", use_container_width=True):
                    chosen_path = os.path.join(VIDEO_DIR, chosen)
                    save_path = os.path.join(VIDEO_DIR, f"individual_video_{session_id}.mp4")
                    shutil.copyfile(chosen_path, save_path)
                    with open(save_path, "rb") as f:
                        file_hash = hashlib.sha256(f.read()).hexdigest()
                    st.session_state[f"media_hash_{person_id}"] = file_hash
                    st.session_state[video_path_key] = save_path
                    reset_person_downstream(person_id)
                    st.rerun()
    else:
        st.markdown("<div style='font-size:1.4rem;font-weight:600;color:var(--tl-text-primary);margin-bottom:1rem;'>VIDEO PREVIEW</div>", unsafe_allow_html=True)
        st.video(st.session_state[video_path_key])
        
        file_size_mb = os.path.getsize(st.session_state[video_path_key]) / (1024*1024)
        st.markdown(f"<div style='font-size:0.9rem;color:var(--tl-text-secondary);margin:0.5rem 0 1.5rem 0;'>File Size: {file_size_mb:.1f} MB</div>", unsafe_allow_html=True)

        if st.button("Analyze Performance", type="primary", use_container_width=True, key="btn_analyze_individual"):
            run_pipeline(person_id, person_label, context_key=active_context_key)
            
        if st.button("Upload a different video", use_container_width=True):
            st.session_state[video_path_key] = None
            reset_person_downstream(person_id)
            st.rerun()

        render_individual_analysis(person_id, person_label)

    st.session_state["individual_video"] = st.session_state.get(video_path_key)
    st.session_state["individual_video_path"] = st.session_state.get(video_path_key)
    st.session_state["individual_transcript"] = st.session_state.get(f"transcript_{person_id}")
    st.session_state["individual_features"] = st.session_state.get(f"speech_features_{person_id}")
    st.session_state["individual_analysis"] = st.session_state.get(f"evaluation_data_{person_id}")


# Backward-compatible alias
render_feature_upload_video = render_feature_individual_video


# ═══════════════════════════════════════════════════════════════════════════════
# FEATURE 3: ⚖️ COMPARE VIDEOS
# ═══════════════════════════════════════════════════════════════════════════════

def render_feature_compare_videos(active_context_key: str) -> None:
    st.markdown(top_navigation_bar_html("Compare", CONTEXT_DISPLAY_NAMES.get(active_context_key, "Job Interview")), unsafe_allow_html=True)
    st.markdown(editorial_page_header_html(
        "COMPARATIVE PERFORMANCE",
        "Side-by-Side Analysis",
        "Analyze two recordings independently and compare their communication performance."
    ), unsafe_allow_html=True)

    session_id = st.session_state.get("_session_id", "default")
    
    col_a, col_vs, col_b = st.columns([1, 0.1, 1])
    
    with col_a:
        st.markdown("### Person A")
        video_a_key = "video_path_a"
        
        if not st.session_state.get(video_a_key):
            upload_a = st.file_uploader("Upload Video A", type=["mp4", "webm", "mov"], key=f"upload_comp_a_{session_id}", label_visibility="hidden")
            if upload_a:
                buf_a = upload_a.getbuffer()
                st.session_state["media_hash_a"] = hashlib.sha256(buf_a).hexdigest()
                path_a = os.path.join(VIDEO_DIR, f"compare_video_a_{session_id}.mp4")
                with open(path_a, "wb") as f:
                    f.write(buf_a)
                st.session_state[video_a_key] = path_a
                reset_person_downstream("a")
                st.rerun()

            test_a_path = os.path.join(VIDEO_DIR, "test_video_a.mp4")
            if os.path.exists(test_a_path):
                with st.expander("Use Sample"):
                    if st.button("Sample Video A", key="btn_sample_comp_a", use_container_width=True):
                        with open(test_a_path, "rb") as f:
                            st.session_state["media_hash_a"] = hashlib.sha256(f.read()).hexdigest()
                        path_a = os.path.join(VIDEO_DIR, f"compare_video_a_{session_id}.mp4")
                        shutil.copyfile(test_a_path, path_a)
                        st.session_state[video_a_key] = path_a
                        reset_person_downstream("a")
                        st.rerun()
        else:
            st.video(st.session_state[video_a_key])
            if st.button("Clear Video A"):
                st.session_state[video_a_key] = None
                reset_person_downstream("a")
                st.rerun()
            if st.session_state.get("evaluation_data_a"):
                st.markdown("✅ **Analyzed**")
                with st.expander("View Details"):
                    render_individual_analysis("a", "Video A")

    with col_vs:
        st.markdown("<div style='height:100%;display:flex;align-items:center;justify-content:center;opacity:0.5;'></div>", unsafe_allow_html=True)
        st.markdown(comparison_vs_nexus_html(), unsafe_allow_html=True)

    with col_b:
        st.markdown("### Person B")
        video_b_key = "video_path_b"
        
        if not st.session_state.get(video_b_key):
            upload_b = st.file_uploader("Upload Video B", type=["mp4", "webm", "mov"], key=f"upload_comp_b_{session_id}", label_visibility="hidden")
            if upload_b:
                buf_b = upload_b.getbuffer()
                st.session_state["media_hash_b"] = hashlib.sha256(buf_b).hexdigest()
                path_b = os.path.join(VIDEO_DIR, f"compare_video_b_{session_id}.mp4")
                with open(path_b, "wb") as f:
                    f.write(buf_b)
                st.session_state[video_b_key] = path_b
                reset_person_downstream("b")
                st.rerun()

            test_b_path = os.path.join(VIDEO_DIR, "test_video_b.mp4")
            if os.path.exists(test_b_path):
                with st.expander("Use Sample"):
                    if st.button("Sample Video B", key="btn_sample_comp_b", use_container_width=True):
                        with open(test_b_path, "rb") as f:
                            st.session_state["media_hash_b"] = hashlib.sha256(f.read()).hexdigest()
                        path_b = os.path.join(VIDEO_DIR, f"compare_video_b_{session_id}.mp4")
                        shutil.copyfile(test_b_path, path_b)
                        st.session_state[video_b_key] = path_b
                        reset_person_downstream("b")
                        st.rerun()
        else:
            st.video(st.session_state[video_b_key])
            if st.button("Clear Video B"):
                st.session_state[video_b_key] = None
                reset_person_downstream("b")
                st.rerun()
            if st.session_state.get("evaluation_data_b"):
                st.markdown("✅ **Analyzed**")
                with st.expander("View Details"):
                    render_individual_analysis("b", "Video B")

    st.markdown("<br><br>", unsafe_allow_html=True)
    
    can_compare = (
        bool(st.session_state.get("evaluation_data_a"))
        and bool(st.session_state.get("evaluation_data_b"))
    )
    both_videos_uploaded = (
        bool(st.session_state.get("video_path_a"))
        and bool(st.session_state.get("video_path_b"))
    )

    if not both_videos_uploaded and not can_compare:
        st.markdown("<p style='text-align:center;color:var(--tl-text-secondary);'>Stage both Person A and Person B above to run the comparison.</p>", unsafe_allow_html=True)
    else:
        btn_label = "Analyze & Compare Performance"
        if st.button(btn_label, type="primary", use_container_width=True, key="btn_compare_exec"):
            if not st.session_state.get("evaluation_data_a"):
                run_pipeline("a", "Video A", context_key=active_context_key)
            if not st.session_state.get("evaluation_data_b"):
                run_pipeline("b", "Video B", context_key=active_context_key)

            if st.session_state.get("evaluation_data_a") and st.session_state.get("evaluation_data_b"):
                with st.spinner("Calculating side-by-side metric deltas and criteria evaluation..."):
                    res = compare_multimodal_performance(
                        eval_a=st.session_state.get("evaluation_data_a"),
                        eval_b=st.session_state.get("evaluation_data_b"),
                        speech_a=st.session_state.get("speech_features_a"),
                        speech_b=st.session_state.get("speech_features_b"),
                        visual_a=st.session_state.get("visual_features_a"),
                        visual_b=st.session_state.get("visual_features_b"),
                        story_a=st.session_state.get("story_data_a"),
                        story_b=st.session_state.get("story_data_b"),
                        profile_key=active_context_key,
                        label_a="Video A",
                        label_b="Video B"
                    )
                    st.session_state["multimodal_comparison"] = res
            else:
                st.markdown("<p style='color:var(--tl-amber-primary);'>Both Video A and Video B must be successfully analyzed before comparison.</p>", unsafe_allow_html=True)

        if st.session_state.get("multimodal_comparison"):
            render_comparison_view(st.session_state["multimodal_comparison"], "Video A", "Video B")

    st.session_state["comparison_video_a"] = st.session_state.get("video_path_a")
    st.session_state["comparison_video_b"] = st.session_state.get("video_path_b")
    st.session_state["comparison_analysis_a"] = st.session_state.get("evaluation_data_a")
    st.session_state["comparison_analysis_b"] = st.session_state.get("evaluation_data_b")


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN ENTRYPOINT
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    init_session_lifecycle()

    # ── Sidebar Luxury Brand & Rail ────────────────────────────────────────────
    st.sidebar.markdown("""
    <div style="display:flex;flex-direction:column;gap:0.2rem;padding:0.5rem 0 1.25rem 0;">
        <div style="display:flex;align-items:center;gap:0.6rem;">
            <div style="width:28px;height:28px;border-radius:8px;background:linear-gradient(135deg,#22c55e,#16a34a);display:flex;align-items:center;justify-content:center;">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#000" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                    <circle cx="12" cy="12" r="3"></circle>
                    <path d="M3 12h3m12 0h3M12 3v3m0 12v3"></path>
                </svg>
            </div>
            <div style="font-family:'Inter',sans-serif;font-size:1.1rem;font-weight:700;color:#fafafa;letter-spacing:-0.02em;">TruthLens <span style="font-size:0.8rem;font-weight:500;color:#22c55e;margin-left:2px;">AI</span></div>
        </div>
        <div style="font-size:0.7rem;color:#a1a1aa;margin-top:0.2rem;margin-left:2.3rem;">Performance Intelligence</div>
    </div>
    """, unsafe_allow_html=True)

    # Canonical Feature Navigation State (Single Source of Truth)
    if "active_feature" not in st.session_state:
        st.session_state["active_feature"] = DEFAULT_FEATURE

    st.sidebar.markdown("<div style='font-size:0.7rem;font-weight:600;color:#71717a;text-transform:uppercase;letter-spacing:0.05em;margin-bottom:0.5rem;'>WORKSPACE</div>", unsafe_allow_html=True)
    selected_feature = st.sidebar.radio(
        "Workspace Navigation",
        label_visibility="collapsed",
        options=ALL_FEATURES,
        key="active_feature"
    )
    st.session_state["sidebar_primary_nav"] = selected_feature

    st.sidebar.markdown(section_divider_glow_html(), unsafe_allow_html=True)
    st.sidebar.markdown("<div style='font-size:0.7rem;font-weight:600;color:#71717a;text-transform:uppercase;letter-spacing:0.05em;margin-bottom:0.3rem;'>CONTEXT</div>", unsafe_allow_html=True)
    context_display = st.sidebar.selectbox(
        "Circumstance Profile:",
        ["💼 Job Interview", "🚀 VC Pitch Presentation", "☕ Casual Team Meeting"],
        key="sidebar_context_selector"
    )
    context_key_map = {
        "💼 Job Interview": CONTEXT_JOB_INTERVIEW,
        "🚀 VC Pitch Presentation": CONTEXT_VC_PITCH,
        "☕ Casual Team Meeting": CONTEXT_CASUAL_MEETING,
    }
    active_context_key = context_key_map.get(context_display, CONTEXT_JOB_INTERVIEW)

    # Invalidate context evaluations when context profile changes
    prev_context = st.session_state.get("_active_context_key")
    if prev_context != active_context_key:
        st.session_state["_active_context_key"] = active_context_key
        for pid in ["live", "upload", "a", "b"]:
            st.session_state[f"evaluation_data_{pid}"] = None
        st.session_state["comparison_result"] = None
        st.session_state["multimodal_comparison"] = None

    # Reset entire session action
    st.sidebar.markdown(section_divider_glow_html(), unsafe_allow_html=True)
    if st.sidebar.button("🔄 Reset Analysis Session", use_container_width=True):
        st.session_state["_session_id"] = uuid.uuid4().hex[:12]
        for pid in ["live", "upload", "a", "b"]:
            reset_person_downstream(pid)
            st.session_state[f"video_path_{pid}"] = None
            st.session_state[f"media_hash_{pid}"] = None
            st.session_state[f"live_mtime_{pid}"] = 0.0
        st.session_state["comparison_result"] = None
        st.session_state["multimodal_comparison"] = None
        st.session_state["_live_was_recording"] = False
        st.session_state["live_recorded_this_session"] = False
        st.rerun()



    # ── Feature Routing (Canonical Single Source of Truth) ─────────────────────
    if selected_feature == FEATURE_LIVE_CAMERA:
        render_feature_live_camera(active_context_key)
    elif selected_feature == FEATURE_INDIVIDUAL_VIDEO:
        render_feature_individual_video(active_context_key)
    elif selected_feature == FEATURE_COMPARE_ASSESS:
        render_feature_compare_videos(active_context_key)
    else:
        render_feature_live_camera(active_context_key)


if __name__ == "__main__":
    main()
