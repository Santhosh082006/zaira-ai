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
)
from processors.context_engine.weighting import get_context_profile, PROFILES
from processors.ingestion.video_demuxer import demux_video_to_audio
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

    st.markdown("---")
    st.header("📊 Communication Performance Assessment")

    assessment_keys = [
        (CAT_CONFIDENCE, "🧠 Confidence Indicators"),
        (CAT_BODY_LANGUAGE, "🧍 Body Language & Posture"),
        (CAT_SPEAKING_STYLE, "🗣️ Speaking Style & Fluency"),
        (CAT_ENGAGEMENT, "👁️ Engagement & Camera Presence"),
        (CAT_STORY_QUALITY, "⭐ Story Quality & Structure")
    ]

    # 1. Overall Communication Score & Five Performance Categories
    if eval_data:
        active_context_key = st.session_state.get("_active_context_key", CONTEXT_JOB_INTERVIEW)
        profile = get_context_profile(active_context_key)
        overall_score, overall_assessment = calculate_overall_communication_score(eval_data, profile)

        # Hero Card: ⭐ Overall Communication Score
        with st.container(border=True):
            if isinstance(overall_score, int):
                color = "🟢" if overall_score >= 80 else "🟡" if overall_score >= 50 else "🔴"
                score_display = f"{color} {overall_score}/100"
            else:
                score_display = f"⚠️ {overall_score}"

            st.markdown(f"## ⭐ Overall Communication Score — {score_display}")
            st.write(overall_assessment)

        # Category Assessments
        for key, title in assessment_keys:
            v = eval_data.get(key)
            if isinstance(v, dict):
                with st.container(border=True):
                    score_val = v.get("score", INSUFFICIENT_DATA)
                    if isinstance(score_val, int):
                        color = "🟢" if score_val >= 80 else "🟡" if score_val >= 50 else "🔴"
                        score_display = f"{color} {score_val}/100"
                    else:
                        score_display = f"⚠️ {score_val}"

                    st.markdown(f"### {title} — {score_display}")
                    if v.get("assessment"):
                        st.write(v.get("assessment"))

                    c_str, c_imp = st.columns(2)
                    with c_str:
                        www = v.get("what_went_well")
                        if www and str(www).strip().upper() != "N/A":
                            st.markdown(f"**Strength:**\n- {www}")
                    with c_imp:
                        wni = v.get("what_needs_improvement")
                        if wni and str(wni).strip().upper() != "N/A":
                            st.markdown(f"**Area for Improvement:**\n- {wni}")

                    rec = v.get("practical_recommendation")
                    if rec and str(rec).strip().upper() != "N/A":
                        st.info(f"💡 **Try this:** {rec}")

                    obs_text = v.get("evidence_observation")
                    if obs_text:
                        if not obs_text.lower().startswith("supporting data:"):
                            obs_text = f"Supporting data: {obs_text}"
                        st.caption(f"📊 {obs_text}")

        # 2. Overall Performance Summary
        st.markdown("---")
        st.subheader("📋 Overall Performance Summary")
        with st.container(border=True):
            c_s1, c_s2 = st.columns(2)
            with c_s1:
                st.markdown("#### ✅ Key Strengths")
                strengths_found = False
                for key, title in assessment_keys:
                    v = eval_data.get(key)
                    if isinstance(v, dict):
                        www = v.get("what_went_well")
                        if www and str(www).strip().upper() != "N/A":
                            st.markdown(f"- **{title}**: {www}")
                            strengths_found = True
                if not strengths_found:
                    st.caption("No specific strengths measured (insufficient multimodal signals).")
            with c_s2:
                st.markdown("#### ⚠️ Priority Improvement Opportunities")
                improvements_found = False
                for key, title in assessment_keys:
                    v = eval_data.get(key)
                    if isinstance(v, dict):
                        wni = v.get("what_needs_improvement")
                        if wni and str(wni).strip().upper() != "N/A":
                            st.markdown(f"- **{title}**: {wni}")
                            improvements_found = True
                if not improvements_found:
                    st.caption("No specific improvements flagged (data unmeasured).")

    # 3. Supporting Analysis Details (After the performance assessment & summary)
    st.markdown("---")
    st.header("🔍 Analysis Details")

    c1, c2 = st.columns([1, 1])
    score, breakdown = calculate_analysis_coverage(person_id)
    with c1:
        with st.container(border=True):
            st.markdown("### 📊 Analysis Coverage")
            color = "🟢" if score > 80 else "🟡" if score > 50 else "🔴"
            st.markdown(f"## {color} {score} / 100")
            for b in breakdown:
                st.markdown(b, unsafe_allow_html=True)
            st.caption("*Measures data completeness and modality availability. Does not measure deception or credibility.*")

    with c2:
        with st.container(border=True):
            st.markdown("### 📄 Spoken Transcript")
            if transcript:
                st.write(transcript)
            else:
                st.caption("No transcript available for this recording.")

    c3, c4 = st.columns(2)
    with c3:
        with st.container(border=True):
            st.markdown("### 🗣️ Observable Speech Signals")
            obs = get_speech_observations(speech_feats)
            for o in obs:
                st.markdown(f"- {o}")
            if speech_feats and speech_feats.get("duration_seconds") is not None:
                st.caption(
                    f"Duration: {speech_feats.get('duration_seconds', 0):.1f}s | "
                    f"Rate: {speech_feats.get('speaking_rate_wpm', 0):.0f} WPM | "
                    f"Pauses: {speech_feats.get('pause_count', 0)}"
                )
            else:
                st.caption("Acoustic metrics: Unavailable (Duration: N/A | Rate: N/A)")
    with c4:
        with st.container(border=True):
            st.markdown("### 👁️ Observable Visual Signals")
            if visual_feats:
                obs = get_visual_observations(visual_feats)
                for o in obs:
                    st.markdown(f"- {o}")
                hm_c = visual_feats.get('head_movement_count', 'N/A')
                hm_r = visual_feats.get('head_movement_rate_per_min')
                hm_disp = f"{hm_c} ({hm_r:.1f}/min, typical: 15-35/min)" if hm_r is not None and hm_c != "N/A" else str(hm_c)
                st.caption(
                    f"Face Presence: {'Yes' if visual_feats.get('face_detected') else 'No'} | "
                    f"Head Movements: {hm_disp} | "
                    f"Blinks: {visual_feats.get('blink_count', 'N/A')}"
                )
            else:
                st.markdown("- No video input provided, visual analysis not applicable.")

    # 4. PDF Export
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
        "📄 Download Performance Report (PDF)",
        data=pdf_bytes,
        file_name=f"TruthLens_Performance_Report_{person_id}.pdf",
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
    st.markdown("---")
    st.header("⚖️ Comparative Performance Assessment")

    # 1. Winner / Outcome Badge
    outcome = comp.get("outcome_badge", "Comparable Result")
    explanation = comp.get("explanation", "")
    if "Video" in outcome:
        st.success(f"### {outcome}")
    elif "Comparable" in outcome:
        st.info(f"### {outcome}")
    else:
        st.warning(f"### {outcome}")

    if explanation:
        st.markdown(f"**Measurement Rationale:** {explanation}")

    # 2. Side-by-Side Metric Deltas
    metric_deltas = comp.get("metric_deltas", [])
    if metric_deltas:
        st.markdown("---")
        st.subheader("📊 Measured Communication Signal Deltas")
        for m in metric_deltas:
            col_m1, col_m2, col_m3 = st.columns([1, 1, 2])
            with col_m1:
                st.metric(f"{label_a} {m['metric']}", m['val_a'])
            with col_m2:
                st.metric(f"{label_b} {m['metric']}", m['val_b'], delta=m['delta'])
            with col_m3:
                st.info(f"💡 {m['interpretation']}")

    # 3. Category Score Deltas
    cat_comps = comp.get("category_comparisons", [])
    if cat_comps:
        st.markdown("---")
        st.subheader("🎯 Performance Category Comparison")
        cols = st.columns(len(cat_comps))
        for idx, c in enumerate(cat_comps):
            with cols[idx]:
                with st.container(border=True):
                    st.markdown(f"**{c['category']}**")
                    st.caption(f"Weight: {c['weight']}")
                    st.write(f"{label_a}: **{c['score_a']}**")
                    st.write(f"{label_b}: **{c['score_b']}**")
                    st.markdown(f"Delta: `{c['delta']}`")
                    st.caption(f"Status: {c['status']}")

    # 4. Narrative / Timeline Differences (if stories exist)
    story_comp = comp.get("story_comparison")
    if story_comp and isinstance(story_comp, dict):
        st.markdown("---")
        st.subheader("📖 Information & Narrative Consistency")
        overall = str(story_comp.get("overall_status", "unclear")).lower()
        if overall == "consistent":
            st.success("🟢 **Narrative Consistency: Consistent** — Both accounts align on chronological events.")
        elif overall == "discrepancies_found":
            st.error("🔴 **Narrative Consistency: Discrepancies Found** — Divergent accounts or conflicting details detected.")
        else:
            st.info(f"ℹ️ **Narrative Consistency: {overall.replace('_', ' ').title()}**")

        summary = story_comp.get("summary")
        if summary:
            st.write(f"**Story Summary:** {summary}")

    # 5. PDF Comparison Export
    st.markdown("---")
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
        "📄 Download Comparison Report (PDF)",
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
    st.title("🎥 Live Camera Recording")
    st.caption("Record yourself speaking naturally, analyze communication signals, and receive evidence-based improvement feedback.")

    person_id = "live"
    person_label = "Live Performer"
    video_path_key = f"video_path_{person_id}"
    session_id = st.session_state.get("_session_id", "default")
    live_video_path = os.path.join(VIDEO_DIR, f"live_session_{session_id}.mp4")

    ctx = None
    c1, c2 = st.columns([1, 1])
    with c1:
        st.subheader("📹 Camera Viewport")
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
                mode=WebRtcMode.SENDONLY,
                rtc_configuration=rtc_config,
                in_recorder_factory=create_recorder,
                media_stream_constraints={"video": True, "audio": True}
            )

            if ctx and ctx.state.playing:
                st.session_state["_live_was_recording"] = True
                st.info("🔴 Recording Active... Speak clearly into your microphone.")
        except Exception as e:
            st.warning(f"Live camera recording component: {e}. You can also use pre-recorded samples.")

    with c2:
        st.subheader("📋 Instructions")
        st.info("""1. Click **START** to turn on your webcam and microphone.
2. Speak naturally for 10–25 seconds.
3. Click **STOP** to finalize your recording.
4. Click **▶️ Analyze Performance** below.""")

        # Quick sample video option if camera not physically available in environment
        sample_path = os.path.join(VIDEO_DIR, "test_video_a.mp4")
        if os.path.exists(sample_path):
            with st.expander("⚡ Load Pre-Recorded Live Test Sample"):
                if st.button("Use Sample Video for Live Camera", key="btn_use_sample_live"):
                    shutil.copyfile(sample_path, live_video_path)
                    with open(live_video_path, "rb") as f:
                        curr_hash = hashlib.sha256(f.read()).hexdigest()
                    st.session_state[f"live_mtime_{person_id}"] = os.path.getmtime(live_video_path)
                    st.session_state[f"media_hash_{person_id}"] = curr_hash
                    st.session_state[video_path_key] = live_video_path
                    st.session_state["live_recorded_this_session"] = True
                    reset_person_downstream(person_id)
                    st.success("Sample loaded for live analysis.")
                    st.rerun()

    # Detect when live recording finishes (recorder was playing, now stopped)
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

    # Action panel when recording is available
    if st.session_state.get(video_path_key) and os.path.exists(st.session_state[video_path_key]):
        st.markdown("---")
        st.success("✅ Recording ready for analysis")
        c_prev, c_act = st.columns([1, 1])
        with c_prev:
            st.video(st.session_state[video_path_key])
        with c_act:
            st.write("Click below to run the multimodal performance assessment.")
            if st.button("▶️ Analyze Performance", type="primary", use_container_width=True, key="btn_analyze_live"):
                run_pipeline(person_id, person_label, context_key=active_context_key)

        # Render performance analysis
        render_individual_analysis(person_id, person_label)

    # Sync friendly aliases
    st.session_state["live_recording"] = st.session_state.get(video_path_key)
    st.session_state["live_video"] = st.session_state.get(video_path_key)
    st.session_state["live_transcript"] = st.session_state.get(f"transcript_{person_id}")
    st.session_state["live_features"] = st.session_state.get(f"speech_features_{person_id}")
    st.session_state["live_analysis"] = st.session_state.get(f"evaluation_data_{person_id}")


# ═══════════════════════════════════════════════════════════════════════════════
# ═══════════════════════════════════════════════════════════════════════════════
# FEATURE 2: 📁 INDIVIDUAL VIDEO ANALYSIS
# ═══════════════════════════════════════════════════════════════════════════════

def render_feature_individual_video(active_context_key: str) -> None:
    st.title("📁 Individual Video Analysis")
    st.caption("Upload a video to receive an individual communication-performance assessment.")

    person_id = "upload"
    person_label = "Individual Performer"
    video_path_key = f"video_path_{person_id}"
    session_id = st.session_state.get("_session_id", "default")

    uploaded_file = st.file_uploader(
        "Upload Video (MP4, WebM, MOV):",
        type=["mp4", "webm", "mov"],
        key=f"uploader_individual_video_{session_id}"
    )

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
            st.success("✅ Video ready for analysis")

    # Also support selecting existing sample from repo for testing
    sample_files = [f for f in os.listdir(VIDEO_DIR) if f.endswith(".mp4")]
    if sample_files and not st.session_state.get(video_path_key):
        with st.expander("⚡ Or Select a Test Video from Repository"):
            chosen = st.selectbox("Choose sample video:", sample_files, key="select_sample_individual")
            if st.button("Load Selected Video", key="btn_load_sample_individual"):
                chosen_path = os.path.join(VIDEO_DIR, chosen)
                save_path = os.path.join(VIDEO_DIR, f"individual_video_{session_id}.mp4")
                shutil.copyfile(chosen_path, save_path)
                with open(save_path, "rb") as f:
                    file_hash = hashlib.sha256(f.read()).hexdigest()
                st.session_state[f"media_hash_{person_id}"] = file_hash
                st.session_state[video_path_key] = save_path
                reset_person_downstream(person_id)
                st.success("Sample video loaded.")
                st.rerun()

    if st.session_state.get(video_path_key) and os.path.exists(st.session_state[video_path_key]):
        st.markdown("---")
        st.success("✅ Video ready for analysis")
        c_prev, c_act = st.columns([1, 1])
        with c_prev:
            st.video(st.session_state[video_path_key])
        with c_act:
            st.write("Click below to run the individual performance assessment.")
            if st.button("▶️ Analyze Performance", type="primary", use_container_width=True, key="btn_analyze_individual"):
                run_pipeline(person_id, person_label, context_key=active_context_key)

        # Render performance analysis
        render_individual_analysis(person_id, person_label)

    # Sync friendly aliases
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
    st.title("⚖️ Compare & Assess")
    st.caption("Analyze two recordings independently and compare measured communication signals side-by-side.")

    session_id = st.session_state.get("_session_id", "default")
    col_a, col_b = st.columns(2)

    # ── VIDEO A PANEL ────────────────────────────────────────────────────────
    with col_a:
        with st.container(border=True):
            st.subheader("📹 Video A")
            video_a_key = "video_path_a"
            upload_a = st.file_uploader("Upload Video A:", type=["mp4", "webm", "mov"], key=f"upload_comp_a_{session_id}")
            if upload_a:
                buf_a = upload_a.getbuffer()
                hash_a = hashlib.sha256(buf_a).hexdigest()
                if st.session_state.get("media_hash_a") != hash_a:
                    st.session_state["media_hash_a"] = hash_a
                    path_a = os.path.join(VIDEO_DIR, f"compare_video_a_{session_id}.mp4")
                    with open(path_a, "wb") as f:
                        f.write(buf_a)
                    st.session_state[video_a_key] = path_a
                    reset_person_downstream("a")
                    st.success("✅ Video A ready")

            # Fallback repo selection for Video A
            test_a_path = os.path.join(VIDEO_DIR, "test_video_a.mp4")
            if not st.session_state.get(video_a_key) and os.path.exists(test_a_path):
                if st.button("⚡ Use Sample Video A (test_video_a.mp4)", key="btn_sample_comp_a"):
                    with open(test_a_path, "rb") as f:
                        st.session_state["media_hash_a"] = hashlib.sha256(f.read()).hexdigest()
                    path_a = os.path.join(VIDEO_DIR, f"compare_video_a_{session_id}.mp4")
                    shutil.copyfile(test_a_path, path_a)
                    st.session_state[video_a_key] = path_a
                    reset_person_downstream("a")
                    st.rerun()

            if st.session_state.get(video_a_key) and os.path.exists(st.session_state[video_a_key]):
                st.video(st.session_state[video_a_key])
                if st.button("▶️ Analyze Video A", type="primary", use_container_width=True, key="btn_run_a"):
                    run_pipeline("a", "Video A", context_key=active_context_key)

            # Concise Video A summary badge and individual results breakdown
            if st.session_state.get("evaluation_data_a"):
                sc_a, _ = calculate_analysis_coverage("a")
                st.success(f"✓ Video A Analyzed (Coverage: {sc_a}/100)")
                with st.expander("📊 View Video A Individual Assessment", expanded=False):
                    render_individual_analysis("a", "Video A")

    # ── VIDEO B PANEL ────────────────────────────────────────────────────────
    with col_b:
        with st.container(border=True):
            st.subheader("📹 Video B")
            video_b_key = "video_path_b"
            upload_b = st.file_uploader("Upload Video B:", type=["mp4", "webm", "mov"], key=f"upload_comp_b_{session_id}")
            if upload_b:
                buf_b = upload_b.getbuffer()
                hash_b = hashlib.sha256(buf_b).hexdigest()
                if st.session_state.get("media_hash_b") != hash_b:
                    st.session_state["media_hash_b"] = hash_b
                    path_b = os.path.join(VIDEO_DIR, f"compare_video_b_{session_id}.mp4")
                    with open(path_b, "wb") as f:
                        f.write(buf_b)
                    st.session_state[video_b_key] = path_b
                    reset_person_downstream("b")
                    st.success("✅ Video B ready")

            # Fallback repo selection for Video B
            test_b_path = os.path.join(VIDEO_DIR, "test_video_b.mp4")
            if not st.session_state.get(video_b_key) and os.path.exists(test_b_path):
                if st.button("⚡ Use Sample Video B (test_video_b.mp4)", key="btn_sample_comp_b"):
                    with open(test_b_path, "rb") as f:
                        st.session_state["media_hash_b"] = hashlib.sha256(f.read()).hexdigest()
                    path_b = os.path.join(VIDEO_DIR, f"compare_video_b_{session_id}.mp4")
                    shutil.copyfile(test_b_path, path_b)
                    st.session_state[video_b_key] = path_b
                    reset_person_downstream("b")
                    st.rerun()

            if st.session_state.get(video_b_key) and os.path.exists(st.session_state[video_b_key]):
                st.video(st.session_state[video_b_key])
                if st.button("▶️ Analyze Video B", type="primary", use_container_width=True, key="btn_run_b"):
                    run_pipeline("b", "Video B", context_key=active_context_key)

            # Concise Video B summary badge and individual results breakdown
            if st.session_state.get("evaluation_data_b"):
                sc_b, _ = calculate_analysis_coverage("b")
                st.success(f"✓ Video B Analyzed (Coverage: {sc_b}/100)")
                with st.expander("📊 View Video B Individual Assessment", expanded=False):
                    render_individual_analysis("b", "Video B")

    # ── COMPARISON TRIGGER & DISPLAY ─────────────────────────────────────────
    st.markdown("---")
    can_compare = (
        bool(st.session_state.get("evaluation_data_a"))
        and bool(st.session_state.get("evaluation_data_b"))
    )
    both_videos_uploaded = (
        bool(st.session_state.get("video_path_a"))
        and bool(st.session_state.get("video_path_b"))
    )

    if not both_videos_uploaded and not can_compare:
        st.info("💡 Upload or select Video A and Video B above to enable comparative assessment.")
    else:
        btn_label = "⚖️ Analyze & Compare" if not can_compare else "⚖️ Compare Measured Performance"
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
                st.error("Both Video A and Video B must be successfully analyzed before comparison.")

        if st.session_state.get("multimodal_comparison"):
            render_comparison_view(st.session_state["multimodal_comparison"], "Video A", "Video B")

    # Sync friendly aliases
    st.session_state["comparison_video_a"] = st.session_state.get("video_path_a")
    st.session_state["comparison_video_b"] = st.session_state.get("video_path_b")
    st.session_state["comparison_analysis_a"] = st.session_state.get("evaluation_data_a")
    st.session_state["comparison_analysis_b"] = st.session_state.get("evaluation_data_b")


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN ENTRYPOINT
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    init_session_lifecycle()

    # ── Sidebar Navigation & Context ───────────────────────────────────────────
    st.sidebar.title("TruthLens")
    feature_mode = st.sidebar.radio(
        "Select Feature:",
        [
            "🎥 Live Camera Recording",
            "📁 Individual Video Analysis",
            "⚖️ Compare & Assess"
        ],
        key="sidebar_primary_nav"
    )

    st.sidebar.markdown("---")
    st.sidebar.markdown("### Evaluation Context")
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
    st.sidebar.markdown("---")
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

    # ── Feature Routing ────────────────────────────────────────────────────────
    if feature_mode == "🎥 Live Camera Recording":
        render_feature_live_camera(active_context_key)
    elif feature_mode == "📁 Individual Video Analysis":
        render_feature_individual_video(active_context_key)
    elif feature_mode == "⚖️ Compare & Assess":
        render_feature_compare_videos(active_context_key)


if __name__ == "__main__":
    main()
