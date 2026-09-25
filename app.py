"""
TruthLens AI - Multimodal Communication & Story Analysis
"""

from __future__ import annotations

import json
import os

import streamlit as st
from audio_recorder_streamlit import audio_recorder
from dotenv import load_dotenv

from services.speech_to_text import load_whisper_model, transcribe_audio
from services.story_analyzer import extract_story_facts, validate_extracted_story, evaluate_individual_account
from services.story_comparator import compare_stories, validate_comparison
from services.llm_provider import get_active_provider
from services.speech_features import extract_speech_features
from services.visual_features import extract_visual_features
from services.media_utils import extract_audio_from_video

# ── Load environment variables from .env file ──────────────────────────────────
load_dotenv()

# ── Constants ──────────────────────────────────────────────────────────────────
AUDIO_DIR = "audio"
VIDEO_DIR = "video"
os.makedirs(AUDIO_DIR, exist_ok=True)
os.makedirs(VIDEO_DIR, exist_ok=True)

# ── Page configuration ─────────────────────────────────────────────────────────
st.set_page_config(
    page_title="TruthLens AI",
    page_icon="🔍",
    layout="wide",
)

# ── Cache the Whisper model so it loads only once per session ──────────────────
@st.cache_resource(
    show_spinner="Loading Whisper model — this may take a moment on first run…"
)
def get_whisper_model():
    return load_whisper_model("base")


# ═══════════════════════════════════════════════════════════════════════════════
# STORY COMPARISON DISPLAY HELPER
# ═══════════════════════════════════════════════════════════════════════════════

def render_comparison(comparison: dict, person_a_label: str = "Person A", person_b_label: str = "Person B") -> None:
    """
    Render the story & communication comparison results in a clear, neutral layout.

    Parameters
    ----------
    comparison : dict
        The dictionary returned by compare_stories().
    person_a_label : str
        Display name for Person A.
    person_b_label : str
        Display name for Person B.
    """
    st.markdown("---")
    st.markdown("## 🔎 Evidence & Consistency Report")

    # ── Communication Comparison (Speech & Visuals) ────────────────────────────
    speech_a = st.session_state.get("speech_features_a")
    speech_b = st.session_state.get("speech_features_b")
    visual_a = st.session_state.get("visual_features_a")
    visual_b = st.session_state.get("visual_features_b")

    if speech_a or speech_b or visual_a or visual_b:
        st.markdown("### 🗣️ Communication Comparison")
        col_c1, col_c2 = st.columns(2)
        with col_c1:
            st.markdown(f"**{person_a_label} Communication Signals:**")
            if speech_a and speech_a.get("reliability_flag") != "analysis_error":
                st.write(f"- Speaking rate: {speech_a.get('speaking_rate_wpm', 0):.0f} WPM")
                st.write(f"- Pauses: {speech_a.get('pause_count', 0)} ({speech_a.get('total_pause_duration_sec', 0):.1f}s)")
                st.write(f"- Filler words: {speech_a.get('filler_word_count', 0)}")
            else:
                st.caption("Speech signals unavailable.")
            if visual_a and visual_a.get("tracking_reliability") != "analysis_error":
                st.write(f"- Face presence: {'Consistent' if visual_a.get('face_detected') else 'Intermittent/None'}")
                st.write(f"- Head movements: {visual_a.get('head_movement_count', 0)} shifts")
            else:
                st.caption("Visual signals unavailable.")

        with col_c2:
            st.markdown(f"**{person_b_label} Communication Signals:**")
            if speech_b and speech_b.get("reliability_flag") != "analysis_error":
                st.write(f"- Speaking rate: {speech_b.get('speaking_rate_wpm', 0):.0f} WPM")
                st.write(f"- Pauses: {speech_b.get('pause_count', 0)} ({speech_b.get('total_pause_duration_sec', 0):.1f}s)")
                st.write(f"- Filler words: {speech_b.get('filler_word_count', 0)}")
            else:
                st.caption("Speech signals unavailable.")
            if visual_b and visual_b.get("tracking_reliability") != "analysis_error":
                st.write(f"- Face presence: {'Consistent' if visual_b.get('face_detected') else 'Intermittent/None'}")
                st.write(f"- Head movements: {visual_b.get('head_movement_count', 0)} shifts")
            else:
                st.caption("Visual signals unavailable.")

        if speech_a and speech_b and speech_a.get("speaking_rate_wpm") and speech_b.get("speaking_rate_wpm"):
            rate_diff = abs(speech_a['speaking_rate_wpm'] - speech_b['speaking_rate_wpm'])
            if rate_diff > 20:
                st.info(f"💡 **Pacing Difference**: {person_a_label} ({speech_a['speaking_rate_wpm']:.0f} WPM) and {person_b_label} ({speech_b['speaking_rate_wpm']:.0f} WPM) spoke at noticeably different tempos (delta: {rate_diff:.0f} WPM).")
        st.markdown("---")

    # ── Overall status badge ────────────────────────────────────────────────────
    overall = str(comparison.get("overall_status", "unclear")).lower()
    status_display = {
        "consistent":              ("🟢", "Consistent",                "success"),
        "discrepancies_found":     ("🔴", "Discrepancies Found",        "error"),
        "missing_information_only":("🟡", "Mostly Consistent (Missing Information)", "warning"),
        "unclear":                 ("⚪", "Unclear",                   "info"),
        "no_data":                 ("⚫", "Insufficient Data",          "info"),
    }
    icon, label, alert_type = status_display.get(
        overall, ("⚪", overall.replace("_", " ").title(), "info")
    )

    if alert_type == "success":
        st.success(f"{icon} **Overall Status: {label}**")
    elif alert_type == "error":
        st.error(f"{icon} **Overall Status: {label}**")
    elif alert_type == "warning":
        st.warning(f"{icon} **Overall Status: {label}**")
    else:
        st.info(f"{icon} **Overall Status: {label}**")

    # ── Overall Summary Statistics ──────────────────────────────────────────────
    summary = comparison.get("summary", "")
    if summary:
        st.markdown(f"**Summary:** {summary}")
        
    st.markdown("---")
    
    timeline = comparison.get("timeline_comparison", [])
    claims = comparison.get("claim_comparison", [])
    
    events_count = len(timeline)
    claims_count = len(claims)
    
    all_items = timeline + claims
    stats = {
        "MATCH": sum(1 for x in all_items if x.get("status") == "MATCH"),
        "PARTIAL_MATCH": sum(1 for x in all_items if x.get("status") == "PARTIAL_MATCH"),
        "CONFLICT": sum(1 for x in all_items if x.get("status") == "CONFLICT"),
        "MISSING_A": sum(1 for x in all_items if x.get("status") == "MISSING_A"),
        "MISSING_B": sum(1 for x in all_items if x.get("status") == "MISSING_B"),
        "UNKNOWN": sum(1 for x in all_items if x.get("status") == "UNKNOWN"),
    }
    
    st.markdown("### 📊 Overall Statistics")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Events Analyzed", events_count)
    c2.metric("Claims Analyzed", claims_count)
    c3.metric("Matches", stats["MATCH"])
    c4.metric("Conflicts", stats["CONFLICT"])
    
    c5, c6, c7, c8 = st.columns(4)
    c5.metric("Partial Matches", stats["PARTIAL_MATCH"])
    c6.metric("Missing in A", stats["MISSING_A"])
    c7.metric("Missing in B", stats["MISSING_B"])
    c8.metric("Unknown", stats["UNKNOWN"])

    st.markdown("---")

    # ── Timeline Comparison ─────────────────────────────────────────────────────
    st.markdown("### 📅 Timeline Comparison")
    if not timeline:
        st.info("No timeline data available yet.")
    else:
        for item in timeline:
            status = item.get("status", "UNKNOWN")
            event_a = item.get("event_a")
            event_b = item.get("event_b")
            
            icon = "🟢" if status == "MATCH" else "🔴" if status == "CONFLICT" else "🟡"
            
            desc_a = event_a.get("description", "—") if isinstance(event_a, dict) else "—"
            desc_b = event_b.get("description", "—") if isinstance(event_b, dict) else "—"
            title_desc = desc_a if status != "MISSING_A" else desc_b
            
            with st.expander(f"{icon} {status}  —  {title_desc}", expanded=(status=="CONFLICT")):
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown("**Person A:**")
                    if isinstance(event_a, dict):
                        st.markdown(event_a.get("description", "—"))
                        if event_a.get("source_text"):
                            st.caption(f"_{event_a.get('source_text')}_")
                    else:
                        st.caption("No event.")
                        
                with col2:
                    st.markdown("**Person B:**")
                    if isinstance(event_b, dict):
                        st.markdown(event_b.get("description", "—"))
                        if event_b.get("source_text"):
                            st.caption(f"_{event_b.get('source_text')}_")
                    else:
                        st.caption("No event.")
                        
                if item.get("reason") or item.get("evidence_points"):
                    st.markdown("---")
                    if item.get("reason"):
                        st.markdown(f"**Why?** {item.get('reason')}")
                    if item.get("evidence_points"):
                        st.markdown("**Evidence points:**")
                        for pt in item.get("evidence_points"):
                            st.markdown(f"• {pt}")
                        
    st.markdown("---")
    
    # ── Claim-Level Comparison ──────────────────────────────────────────────────
    st.markdown("### 🔎 Claim-Level Comparison")
    if not claims:
        st.info("No claim data available yet.")
    else:
        for claim in claims:
            status = claim.get("status", "UNKNOWN")
            subject = claim.get("subject", "Unknown Subject")
            attribute = claim.get("attribute", "Unknown Attribute")
            
            icon = "🟢" if status == "MATCH" else "🔴" if status == "CONFLICT" else "🟡"
            
            person_a = claim.get("person_a")
            person_b = claim.get("person_b")
            
            with st.expander(f"{icon} {status}  —  {subject} ({attribute})", expanded=(status=="CONFLICT")):
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown("**Person A:**")
                    if isinstance(person_a, dict):
                        st.markdown(person_a.get("value", "—"))
                        if person_a.get("source_text"):
                            st.caption(f"_{person_a.get('source_text')}_")
                    else:
                        st.caption("No claim.")
                        
                with col2:
                    st.markdown("**Person B:**")
                    if isinstance(person_b, dict):
                        st.markdown(person_b.get("value", "—"))
                        if person_b.get("source_text"):
                            st.caption(f"_{person_b.get('source_text')}_")
                    else:
                        st.caption("No claim.")

                if claim.get("reason") or claim.get("evidence_points"):
                    st.markdown("---")
                    if claim.get("reason"):
                        st.markdown(f"**Why?** {claim.get('reason')}")
                    if claim.get("evidence_points"):
                        st.markdown("**Evidence points:**")
                        for pt in claim.get("evidence_points"):
                            st.markdown(f"• {pt}")

    st.markdown("---")

    # ── Layout: three columns for the main finding categories ──────────────────
    matches      = comparison.get("matches", [])
    discrepancies = comparison.get("discrepancies", [])
    missing      = comparison.get("missing_information", [])
    unclear      = comparison.get("unclear_information", [])

    col_left, col_right = st.columns(2)

    # ── Agreements ──────────────────────────────────────────────────────────────
    with col_left:
        st.markdown(f"### ✅ Agreements ({len(matches)})")
        if not matches:
            st.caption("No matching facts found between the two stories.")
        for m in matches:
            cat  = str(m.get("category", "")).capitalize()
            a_val = m.get("person_a_value", "—")
            b_val = m.get("person_b_value", "—")
            desc  = m.get("description", "")
            with st.expander(f"✓ {cat}  —  {desc or a_val}", expanded=False):
                c1, c2 = st.columns(2)
                c1.markdown(f"**Person A:** {a_val}")
                c2.markdown(f"**Person B:** {b_val}")

    # ── Conflicts ────────────────────────────────────────────────────────────────
    with col_right:
        st.markdown(f"### ⚠️ Conflicts ({len(discrepancies)})")
        if not discrepancies:
            st.caption("No outright conflicts found.")
        for d in discrepancies:
            cat   = str(d.get("category", "")).capitalize()
            a_val = d.get("person_a_value", "—")
            b_val = d.get("person_b_value", "—")
            desc  = d.get("description", "")
            with st.expander(f"⚠️ {cat}  —  {desc or 'See details'}", expanded=True):
                c1, c2 = st.columns(2)
                c1.markdown(f"**Person A:** {a_val}")
                c2.markdown(f"**Person B:** {b_val}")
                if desc:
                    st.caption(f"Note: {desc}")

    st.markdown("---")
    col_miss, col_unclear = st.columns(2)

    # ── Missing Details ──────────────────────────────────────────────────────────
    with col_miss:
        st.markdown(f"### ℹ️ Missing Details ({len(missing)})")
        if not missing:
            st.caption("No one-sided information found.")
        for mi in missing:
            cat       = str(mi.get("category", "")).capitalize()
            present   = mi.get("present_in", "?")
            absent    = mi.get("absent_in", "?")
            value     = mi.get("value", "—")
            desc      = mi.get("description", "")
            with st.expander(f"ℹ️ {cat}  —  mentioned by {present} only", expanded=True):
                st.markdown(f"**{present} mentioned:** {value}")
                st.markdown(f"**{absent} did not mention this.**")
                if desc:
                    st.caption(desc)

    # ── Unclear information ──────────────────────────────────────────────────────
    with col_unclear:
        st.markdown(f"### ❓ Unclear ({len(unclear)})")
        if not unclear:
            st.caption("No unclear information found.")
        for u in unclear:
            cat  = str(u.get("category", "")).capitalize()
            desc = u.get("description", "—")
            with st.expander(f"❓ {cat}", expanded=False):
                st.markdown(desc)

    # ── Raw JSON debug ───────────────────────────────────────────────────────────
    st.markdown("---")
    with st.expander("🔍 Detailed Comparison Data", expanded=False):
        st.json(comparison)


# ═══════════════════════════════════════════════════════════════════════════════
# PERSON RECORDING PANEL
# ═══════════════════════════════════════════════════════════════════════════════



# ═══════════════════════════════════════════════════════════════════════════════
# UI HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def get_speech_observations(feats):
    if not feats or feats.get("reliability_flag") == "analysis_error":
        return ["Speech analysis unavailable for this audio."]
    obs = []
    wpm = feats.get("speaking_rate_wpm")
    if wpm is not None:
        if wpm < 110: obs.append(f"Speech was relatively slow ({wpm:.0f} WPM), which may indicate a deliberate speaking pace.")
        elif wpm > 160: obs.append(f"Fast speaking pace observed ({wpm:.0f} WPM).")
        else: obs.append(f"Normal conversational speaking pace ({wpm:.0f} WPM).")
    
    fillers = feats.get("filler_word_count")
    if fillers is not None:
        if fillers == 0: obs.append("Very few filler words were detected, suggesting relatively clean verbal delivery.")
        elif fillers > 10: obs.append("Frequent filler words detected.")
    
    pauses = feats.get("pause_count")
    if pauses is not None:
        if pauses > 2: obs.append("Several longer pauses were detected. These may indicate hesitation, thinking time, or natural breaks.")
        elif pauses == 0: obs.append("Few or no long pauses detected, suggesting fluid delivery.")
    
    if not obs:
        obs.append("Acoustic features were extracted but no distinct observations were flagged.")
    return obs

def get_visual_observations(v_feats):
    if not v_feats or v_feats.get("tracking_reliability") == "analysis_error":
        return ["Visual analysis unavailable for this video."]
    obs = []
    if v_feats.get("face_detected"):
        obs.append("Face was consistently visible during the analyzed portion of the recording.")
    else:
        obs.append("Face was frequently obscured or not detected.")
        
    hm = v_feats.get("head_movement_count")
    if hm is not None:
        if hm > 15: obs.append("Frequent head movement was observed during the recording.")
        else: obs.append("Head position remained relatively stable.")
        
    obs.append("Visual attention appeared relatively stable during the analyzed frames.")
    return obs

def calculate_analysis_coverage(person_id):
    has_text = bool((st.session_state.get(f"transcript_{person_id}") or "").strip())
    has_audio = bool(st.session_state.get(f"audio_path_{person_id}"))
    has_video = bool(st.session_state.get(f"video_path_{person_id}"))
    has_story = bool(st.session_state.get(f"story_data_{person_id}"))
    has_speech = bool(st.session_state.get(f"speech_features_{person_id}"))
    has_visual = bool(st.session_state.get(f"visual_features_{person_id}"))
    has_eval = bool(st.session_state.get(f"evaluation_data_{person_id}"))

    breakdown = []
    total_checks = 0
    passed_checks = 0

    if has_audio or has_video or has_text:
        breakdown.append("Input Data&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;✅ Available")
        total_checks += 1
        passed_checks += 1
    else:
        breakdown.append("Input Data&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;❌ Unavailable")
        total_checks += 1

    if has_text:
        breakdown.append("Transcript&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;✅ Complete")
        passed_checks += 1
    else:
        breakdown.append("Transcript&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;❌ Unavailable")
    total_checks += 1

    if has_audio or has_video:
        total_checks += 1
        if has_speech:
            breakdown.append("Speech Analysis&nbsp;✅ Complete")
            passed_checks += 1
        else:
            breakdown.append("Speech Analysis&nbsp;❌ Failed/Unavailable")

    if has_video:
        total_checks += 1
        if has_visual:
            breakdown.append("Visual Analysis&nbsp;✅ Complete")
            passed_checks += 1
        else:
            breakdown.append("Visual Analysis&nbsp;❌ Failed/Unavailable")
            
    total_checks += 1
    if has_story:
        breakdown.append("Story Analysis&nbsp;&nbsp;✅ Complete")
        passed_checks += 1
    else:
        breakdown.append("Story Analysis&nbsp;&nbsp;❌ Unavailable")

    total_checks += 1
    if has_eval:
        if not has_text or (has_video and not has_visual) or (has_audio and not has_speech):
            breakdown.append("Individual Eval&nbsp;⚠️ Partial")
            passed_checks += 0.5
        else:
            breakdown.append("Individual Eval&nbsp;✅ Complete")
            passed_checks += 1
    else:
        breakdown.append("Individual Eval&nbsp;❌ Unavailable")

    score = int((passed_checks / max(1, total_checks)) * 100)
    return score, breakdown


# ═══════════════════════════════════════════════════════════════════════════════
# INDIVIDUAL ANALYSIS RENDERER
# ═══════════════════════════════════════════════════════════════════════════════

def render_individual_analysis(person_id: str, person_label: str):
    story = st.session_state.get(f"story_data_{person_id}")
    eval_data = st.session_state.get(f"evaluation_data_{person_id}")
    transcript = (st.session_state.get(f"transcript_{person_id}") or "").strip()
    speech_feats = st.session_state.get(f"speech_features_{person_id}")
    visual_feats = st.session_state.get(f"visual_features_{person_id}")
    video_path = st.session_state.get(f"video_path_{person_id}")
    audio_path = st.session_state.get(f"audio_path_{person_id}")

    has_any_results = any([transcript, speech_feats, visual_feats, story, eval_data])

    if not has_any_results:
        if video_path or audio_path:
            st.info(f"ℹ️ Recording ready. Click '▶️ Analyze' above to run performance analysis.")
        else:
            st.info("No recording captured yet. Please record above.")
        return

    st.markdown(f"### 📊 {person_label} Performance Analysis")

    # 1. Coverage & Overview
    c1, c2 = st.columns([1, 1])
    score, breakdown = calculate_analysis_coverage(person_id)
    with c1:
        with st.container(border=True):
            st.markdown("#### 📊 Analysis Coverage")
            color = "🟢" if score > 80 else "🟡" if score > 50 else "🔴"
            st.markdown(f"## {color} {score} / 100")
            for b in breakdown:
                st.markdown(b, unsafe_allow_html=True)
            st.caption("*Analysis Coverage measures how complete and usable the available information is for analysis. It does not measure truthfulness, honesty, or credibility.*")

    with c2:
        with st.container(border=True):
            st.markdown("#### 📄 Transcript")
            if transcript:
                st.write(transcript)
            else:
                st.caption("⚠️ Automatic transcription unavailable for this recording. You may enter a transcript manually above.")

    # 2. Observable Signals (Speech & Visual)
    c3, c4 = st.columns(2)
    with c3:
        with st.container(border=True):
            st.markdown("#### 🗣️ Speaking Style & Fluency Signals")
            obs = get_speech_observations(speech_feats)
            for o in obs:
                st.markdown(f"- {o}")
            if speech_feats and speech_feats.get("duration_seconds"):
                st.caption(f"Duration: {speech_feats.get('duration_seconds', 0):.1f}s | Words: {speech_feats.get('word_count', 0)} | Rate: {speech_feats.get('speaking_rate_wpm', 0):.0f} WPM")
    with c4:
        with st.container(border=True):
            st.markdown("#### 👁️ Body Language & Visual Signals")
            if visual_feats:
                obs = get_visual_observations(visual_feats)
                for o in obs:
                    st.markdown(f"- {o}")
                st.caption(f"Face Presence: {'Yes' if visual_feats.get('face_detected') else 'No'} | Head Movements: {visual_feats.get('head_movement_count', 'N/A')} | Blinks: {visual_feats.get('blink_count', 'N/A')}")
            else:
                st.markdown("- No video input provided, visual analysis not applicable.")

    # 3. Story Understanding (if extracted)
    if story:
        with st.container(border=True):
            st.markdown("#### 📖 Story Understanding & Content")
            st.markdown(f"**Summary:** {story.get('summary', '')}")
            col_ev, col_cl = st.columns(2)
            with col_ev:
                st.markdown("**Events Timeline**")
                for e in story.get("events", []):
                    with st.expander(f"{e.get('time', 'Unknown time')} - {e.get('location', 'Unknown location')}"):
                        st.write(e.get("description"))
            with col_cl:
                st.markdown("**Key Claims**")
                for c in story.get("claims", []):
                    with st.expander(f"{c.get('subject')} - {c.get('value')}"):
                        st.write(c.get("source_text"))

    # 4. Evidence-Backed Performance Assessments
    if eval_data:
        st.markdown("#### 🎯 Performance & Communication Assessment")
        
        assessment_keys = [
            ("confidence_indicators", "🧠 Confidence Indicators"),
            ("body_language", "🧍 Body Language & Posture"),
            ("speaking_style", "🗣️ Speaking Style"),
            ("engagement", "👁️ Engagement & Camera Presence"),
            ("story_quality", "⭐ Story Quality & Structure")
        ]
        
        for key, title in assessment_keys:
            v = eval_data.get(key)
            if isinstance(v, dict):
                with st.container(border=True):
                    score_val = v.get("score", "Insufficient Data")
                    if isinstance(score_val, int):
                        color = "🟢" if score_val >= 80 else "🟡" if score_val >= 50 else "🔴"
                        score_display = f"{color} {score_val}/100"
                    else:
                        score_display = f"⚠️ {score_val}"
                    
                    st.markdown(f"##### {title} — {score_display}")
                    
                    if v.get("assessment"):
                        st.write(f"**Assessment:** {v.get('assessment')}")
                    if v.get("evidence_observation"):
                        st.caption(f"**Evidence / Observation:** {v.get('evidence_observation')}")
                        
                    c_str, c_imp = st.columns(2)
                    with c_str:
                        if v.get("what_went_well"):
                            st.markdown(f"**What Went Well:**\n- {v.get('what_went_well')}")
                    with c_imp:
                        if v.get("what_needs_improvement"):
                            st.markdown(f"**What Needs Improvement:**\n- {v.get('what_needs_improvement')}")
                    
                    if v.get("practical_recommendation"):
                        st.info(f"💡 **Actionable Recommendation:** {v.get('practical_recommendation')}")

        # 5. Overall Performance Summary
        st.markdown("#### 📋 Overall Performance Summary")
        with st.container(border=True):
            c_s1, c_s2 = st.columns(2)
            with c_s1:
                st.markdown("##### ✅ Core Strengths")
                for key, title in assessment_keys:
                    v = eval_data.get(key)
                    if isinstance(v, dict) and v.get("what_went_well"):
                        st.markdown(f"- **{title}**: {v.get('what_went_well')}")
            with c_s2:
                st.markdown("##### ⚠️ Priority Improvement Areas")
                for key, title in assessment_keys:
                    v = eval_data.get(key)
                    if isinstance(v, dict) and v.get("what_needs_improvement"):
                        st.markdown(f"- **{title}**: {v.get('what_needs_improvement')}")


# ═══════════════════════════════════════════════════════════════════════════════
# UNIFIED PIPELINE RUNNER
# ═══════════════════════════════════════════════════════════════════════════════

def run_pipeline(person_id: str, person_label: str) -> bool:
    """
    Executes the multimodal pipeline for person_id:
    Extract audio -> Transcribe -> Speech Analysis -> Visual Analysis -> Story -> Individual Eval.
    """
    video_path_key      = f"video_path_{person_id}"
    audio_path_key      = f"audio_path_{person_id}"
    audio_key           = f"audio_bytes_{person_id}"
    transcript_key      = f"transcript_{person_id}"
    speech_features_key = f"speech_features_{person_id}"
    visual_features_key = f"visual_features_{person_id}"
    story_key           = f"story_data_{person_id}"
    eval_key            = f"evaluation_data_{person_id}"

    with st.status(f"🔄 Processing {person_label}...", expanded=True) as status:
        try:
            # 1. Video -> Audio extraction
            if st.session_state.get(video_path_key) and not st.session_state.get(audio_path_key):
                st.write("⏳ Extracting audio from video...")
                try:
                    extracted_path = os.path.join(AUDIO_DIR, f"person_{person_id}_extracted.wav")
                    extract_audio_from_video(st.session_state[video_path_key], extracted_path)
                    st.session_state[audio_path_key] = extracted_path
                    with open(extracted_path, "rb") as f:
                        st.session_state[audio_key] = f.read()
                    st.write("✓ Audio extracted")
                except Exception as e:
                    st.write(f"⚠️ Audio extraction failed: {e}")

            # 2. Transcription
            if st.session_state.get(audio_path_key) and not (st.session_state.get(transcript_key) or "").strip():
                st.write("⏳ Transcribing audio...")
                success = False
                
                try:
                    from services.speech_to_text import transcribe_audio
                    model = get_whisper_model()
                    text = transcribe_audio(model, st.session_state[audio_path_key])
                    st.session_state[transcript_key] = text
                    st.session_state[f"_sync_transcript_{person_id}"] = True
                    st.write("✓ Local Whisper: Available and Complete")
                    success = True
                except Exception as e:
                    st.write(f"⚠️ Local Whisper: Failed ({str(e)})")
                    
                if not success:
                    groq_key = os.getenv("GROQ_API_KEY")
                    openai_key = os.getenv("OPENAI_API_KEY")
                    if groq_key:
                        st.write("⏳ Local Whisper unavailable. Using configured transcription provider (Groq)...")
                        try:
                            from groq import Groq
                            client = Groq(api_key=groq_key)
                            with open(st.session_state[audio_path_key], "rb") as file:
                                transcription = client.audio.transcriptions.create(file=(st.session_state[audio_path_key], file.read()), model="whisper-large-v3-turbo")
                            st.session_state[transcript_key] = transcription.text
                            st.session_state[f"_sync_transcript_{person_id}"] = True
                            st.write("✓ Fallback transcription: Available")
                            success = True
                        except Exception as cloud_e:
                            st.write(f"⚠️ Fallback transcription: Failed ({str(cloud_e)})")
                    elif openai_key:
                        st.write("⏳ Local Whisper unavailable. Using configured transcription provider (OpenAI)...")
                        try:
                            from openai import OpenAI
                            client = OpenAI(api_key=openai_key)
                            with open(st.session_state[audio_path_key], "rb") as audio_file:
                                transcription = client.audio.transcriptions.create(model="whisper-1", file=audio_file)
                            st.session_state[transcript_key] = transcription.text
                            st.session_state[f"_sync_transcript_{person_id}"] = True
                            st.write("✓ Fallback transcription: Available")
                            success = True
                        except Exception as cloud_e:
                            st.write(f"⚠️ Fallback transcription: Failed ({str(cloud_e)})")
                            
                if not success:
                    st.write("⚠️ Automatic transcription unavailable. Please provide a transcript manually.")
                    st.session_state[transcript_key] = ""
                    st.session_state[f"_sync_transcript_{person_id}"] = True

            # 3. Speech analysis
            if st.session_state.get(audio_path_key) and not st.session_state.get(speech_features_key):
                st.write("⏳ Analyzing speech signals...")
                try:
                    feats = extract_speech_features(st.session_state[audio_path_key], st.session_state.get(transcript_key, ""))
                    st.session_state[speech_features_key] = feats
                    st.write("✓ Speech analyzed")
                except Exception as e:
                    st.write(f"⚠️ Speech analysis unavailable: {e}")

            # 4. Visual analysis
            if st.session_state.get(video_path_key) and not st.session_state.get(visual_features_key):
                st.write("⏳ Analyzing visual signals...")
                try:
                    v_feats = extract_visual_features(st.session_state[video_path_key])
                    st.session_state[visual_features_key] = v_feats
                    st.write("✓ Visual observations analyzed")
                except Exception as e:
                    st.write(f"⚠️ Visual analysis unavailable: {e}")
            
            # 5. Story analysis (if transcript exists)
            if (st.session_state.get(transcript_key) or "").strip() and not st.session_state.get(story_key):
                st.write("⏳ Understanding story...")
                try:
                    provider_label = get_active_provider()
                    story_data = extract_story_facts(transcript=st.session_state[transcript_key], person_name=person_label)
                    is_valid, errs = validate_extracted_story(story_data)
                    if not is_valid: raise RuntimeError("Story schema error: " + "; ".join(errs))
                    st.session_state[story_key] = story_data
                    st.write("✓ Story understood")
                except Exception as e:
                    st.write(f"⚠️ Story analysis unavailable: {e}")

            # 6. Performance assessment
            st.write("⏳ Generating performance assessment...")
            try:
                eval_data = evaluate_individual_account(
                    person_name=person_label,
                    transcript=st.session_state.get(transcript_key, ""),
                    story_data=st.session_state.get(story_key),
                    speech_feats=st.session_state.get(speech_features_key),
                    visual_feats=st.session_state.get(visual_features_key)
                )
                st.session_state[eval_key] = eval_data
                score, _ = calculate_analysis_coverage(person_id)
                st.write("✓ Performance assessment generated")
            except Exception as e:
                st.write(f"⚠️ Assessment error: {e}")

            status.update(label=f"✓ {person_label} Analysis Complete", state="complete", expanded=False)
            return True
        except Exception as e:
            st.error(f"❌ Processing stopped: {str(e)}")
            status.update(label=f"❌ {person_label} Processing Failed", state="error", expanded=True)
            return False


# ═══════════════════════════════════════════════════════════════════════════════
# PERSON RECORDING & PROCESSING PANEL (FOR DUAL COMPARISON)
# ═══════════════════════════════════════════════════════════════════════════════

def render_person_panel(person_id: str, person_label: str) -> None:
    """
    Render the multimodal input and processing controls for Person A or Person B.
    """
    audio_key           = f"audio_bytes_{person_id}"
    transcript_key      = f"transcript_{person_id}"
    audio_path_key      = f"audio_path_{person_id}"
    story_key           = f"story_data_{person_id}"
    speech_features_key = f"speech_features_{person_id}"
    video_path_key      = f"video_path_{person_id}"
    visual_features_key = f"visual_features_{person_id}"
    eval_key            = f"evaluation_data_{person_id}"
    input_mode_key      = f"input_mode_{person_id}"

    for key, default in [
        (audio_key,           None),
        (transcript_key,      ""),
        (audio_path_key,      ""),
        (story_key,           None),
        (speech_features_key, None),
        (video_path_key,      None),
        (visual_features_key, None),
        (eval_key,            None),
        (input_mode_key,      "🎙️ Record Audio")
    ]:
        if key not in st.session_state:
            st.session_state[key] = default

    st.subheader(f"🎤 {person_label}")

    def reset_downstream():
        st.session_state[transcript_key] = ""
        st.session_state[f"_sync_transcript_{person_id}"] = True
        st.session_state[story_key] = None
        st.session_state[speech_features_key] = None
        st.session_state[visual_features_key] = None
        st.session_state[eval_key] = None
        st.session_state["comparison_result"] = None

    def on_transcript_edit():
        st.session_state[story_key] = None
        st.session_state[speech_features_key] = None
        st.session_state[eval_key] = None
        st.session_state["comparison_result"] = None

    input_options = ["🎙️ Record Audio", "🎵 Upload Audio", "🎥 Upload Video", "📝 Enter Transcript"]
    selected_mode = st.radio("Select Input Method", input_options, horizontal=True, key=f"radio_mode_{person_id}")

    if selected_mode == "🎙️ Record Audio":
        audio_bytes = audio_recorder(text="", key=f"recorder_{person_id}")
        if audio_bytes and len(audio_bytes) > 0:
            if st.session_state.get(audio_key) != audio_bytes:
                st.session_state[audio_key] = audio_bytes
                audio_path = os.path.join(AUDIO_DIR, f"person_{person_id}_story.wav")
                with open(audio_path, "wb") as f: f.write(audio_bytes)
                st.session_state[audio_path_key] = audio_path
                st.session_state[video_path_key] = None
                reset_downstream()
                st.success("✅ Recording saved!")
    elif selected_mode == "🎵 Upload Audio":
        audio_upload = st.file_uploader("Upload Audio file", type=["wav", "mp3", "m4a"], key=f"audio_upload_{person_id}")
        if audio_upload:
            import hashlib
            buffer = audio_upload.getbuffer()
            file_hash = hashlib.sha256(buffer).hexdigest()
            if st.session_state.get(f"media_hash_{person_id}") != file_hash:
                st.session_state[f"media_hash_{person_id}"] = file_hash
                audio_path = os.path.join(AUDIO_DIR, f"person_{person_id}_upload.wav")
                with open(audio_path, "wb") as f: f.write(buffer)
                st.session_state[audio_path_key] = audio_path
                st.session_state[video_path_key] = None
                st.session_state[audio_key] = buffer
                reset_downstream()
                st.success("✅ Audio uploaded!")
    elif selected_mode == "🎥 Upload Video":
        video_upload = st.file_uploader("Upload Video file", type=["mp4", "webm", "mov"], key=f"video_upload_{person_id}")
        if video_upload:
            import hashlib
            buffer = video_upload.getbuffer()
            file_hash = hashlib.sha256(buffer).hexdigest()
            if st.session_state.get(f"media_hash_{person_id}") != file_hash:
                st.session_state[f"media_hash_{person_id}"] = file_hash
                video_path = os.path.join(VIDEO_DIR, f"person_{person_id}_upload.mp4")
                with open(video_path, "wb") as f: f.write(buffer)
                st.session_state[video_path_key] = video_path
                st.session_state[audio_path_key] = None
                st.session_state[audio_key] = None
                reset_downstream()
                st.success("✅ Video uploaded!")
        if st.session_state.get(video_path_key):
            st.video(st.session_state[video_path_key])

    textarea_key = f"textarea_{person_id}"
    if textarea_key not in st.session_state or st.session_state.get(f"_sync_transcript_{person_id}"):
        st.session_state[textarea_key] = st.session_state[transcript_key]
        st.session_state[f"_sync_transcript_{person_id}"] = False

    current_transcript = st.text_area("Transcript", height=120, key=textarea_key, on_change=on_transcript_edit)
    if current_transcript != st.session_state[transcript_key]:
        st.session_state[transcript_key] = current_transcript or ""

    can_process = bool(st.session_state.get(audio_path_key)) or bool(st.session_state.get(video_path_key)) or bool((st.session_state.get(transcript_key) or "").strip())
    
    if st.button(f"▶️ Analyze {person_label}", type="primary", use_container_width=True, disabled=not can_process):
        run_pipeline(person_id, person_label)

    # ── Display Analysis Results below the input/process area
    st.markdown("---")
    render_individual_analysis(person_id, person_label)


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN UI LAYOUT
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    st.sidebar.title("TruthLens")
    app_mode = st.sidebar.radio("Select Feature:", ["🎥 Live Camera Recording", "⚖️ Compare & Assess"])
    
    st.title("TruthLens AI")
    if app_mode == "🎥 Live Camera Recording":
        st.caption("Record yourself speaking, analyze your communication dynamics, and receive actionable improvements.")
    else:
        st.caption("Analyze two recordings independently and compare communication patterns, stories, and consistency.")

    # App-level actions
    c1, c2, c3 = st.columns([1,1,2])
    with c1:
        if st.button("🔄 Start New Analysis", use_container_width=True, type="primary"):
            for pk in ["a", "b"]:
                for key in ["audio_bytes", "transcript", "textarea", "audio_path", "story_data", "speech_features", "video_path", "visual_features", "evaluation_data", "media_hash", "media_source", "live_recorded_mtime"]:
                    if key in ["transcript", "textarea"]:
                        st.session_state[f"{key}_{pk}"] = ""
                    elif key == "live_recorded_mtime":
                        st.session_state[f"{key}_{pk}"] = 0
                    else:
                        st.session_state[f"{key}_{pk}"] = None
            st.session_state["comparison_result"] = None
            st.rerun()
    with c2:
        if st.button("🧪 Load Demo Analysis", use_container_width=True):
            st.session_state["transcript_a"] = "After class, I walked to the campus library around 3:00 PM. I sat at a table with John and we studied for exactly one hour. Afterward, I went down to the cafe to grab a coffee."
            st.session_state["textarea_a"] = st.session_state["transcript_a"]
            st.session_state["transcript_b"] = "After class ended, I headed over to the campus library at 3:30 PM. I saw him there, but he was studying alone for about two hours. I didn't see him go to the cafe."
            st.session_state["textarea_b"] = st.session_state["transcript_b"]
            for pk in ["a", "b"]:
                st.session_state[f"audio_bytes_{pk}"] = None
                st.session_state[f"audio_path_{pk}"] = None
                st.session_state[f"story_data_{pk}"] = None
                st.session_state[f"speech_features_{pk}"] = None
                st.session_state[f"video_path_{pk}"] = None
                st.session_state[f"visual_features_{pk}"] = None
                st.session_state[f"evaluation_data_{pk}"] = None
            st.session_state["comparison_result"] = None
            st.rerun()

    st.markdown("---")
    
    if app_mode == "🎥 Live Camera Recording":
        person_id = "a"
        person_label = "Performer"
        video_path_key = f"video_path_{person_id}"
        transcript_key = f"transcript_{person_id}"
        live_video_path = os.path.join(VIDEO_DIR, f"live_session_{person_id}.mp4")

        st.markdown("### 🎥 Live Camera Recording")
        st.write("Ensure camera and microphone permissions are granted in the browser.")
        
        ctx = None
        c1, c2 = st.columns([1, 1])
        with c1:
            try:
                import streamlit_webrtc
                from streamlit_webrtc import webrtc_streamer, WebRtcMode, RTCConfiguration
                from aiortc.contrib.media import MediaRecorder
                
                def create_recorder():
                    return MediaRecorder(live_video_path)
                
                rtc_config = RTCConfiguration(
                    {"iceServers": [{"urls": ["stun:stun.l.google.com:19302"]}]}
                )
                ctx = webrtc_streamer(
                    key="live_capture",
                    mode=WebRtcMode.SENDONLY,
                    rtc_configuration=rtc_config,
                    in_recorder_factory=create_recorder,
                    media_stream_constraints={"video": True, "audio": True}
                )
                
                if ctx and ctx.state.playing:
                    st.info("🔴 Recording Active... Speak clearly into your microphone.")
            except Exception as e:
                st.warning(f"Live camera/microphone is unavailable in this environment ({e}).")

        with c2:
            st.info("""💡 **Instructions**:
1. Click **START** to begin.
2. Speak naturally for 10–20 seconds.
3. Click **STOP** to finish recording.
4. Review your session below and click **▶️ Analyze Live Session**.""")

        # Independent File Detection & Handoff for Live Recording
        if os.path.exists(live_video_path) and os.path.getsize(live_video_path) > 0:
            import hashlib
            live_mtime = os.path.getmtime(live_video_path)
            prev_live_mtime = st.session_state.get(f"live_recorded_mtime_{person_id}") or 0
            
            with open(live_video_path, "rb") as f:
                curr_hash = hashlib.sha256(f.read()).hexdigest()
            
            is_new_live = live_mtime > prev_live_mtime + 0.5
            if (is_new_live and st.session_state.get(f"media_hash_{person_id}") != curr_hash) or (not st.session_state.get(video_path_key) and st.session_state.get(f"media_source_{person_id}") != "upload"):
                st.session_state[f"live_recorded_mtime_{person_id}"] = live_mtime
                st.session_state[f"media_source_{person_id}"] = "live"
                st.session_state[f"media_hash_{person_id}"] = curr_hash
                st.session_state[video_path_key] = live_video_path
                st.session_state[f"audio_path_{person_id}"] = None
                st.session_state[f"audio_bytes_{person_id}"] = None
                st.session_state[transcript_key] = ""
                st.session_state[f"_sync_transcript_{person_id}"] = True
                st.session_state[f"story_data_{person_id}"] = None
                st.session_state[f"speech_features_{person_id}"] = None
                st.session_state[f"visual_features_{person_id}"] = None
                st.session_state[f"evaluation_data_{person_id}"] = None
            elif not st.session_state.get(video_path_key) and st.session_state.get(f"media_source_{person_id}") != "upload":
                st.session_state[video_path_key] = live_video_path

        # Fallback Video Upload
        has_video = bool(st.session_state.get(video_path_key)) and os.path.exists(st.session_state[video_path_key]) and os.path.getsize(st.session_state[video_path_key]) > 0
        with st.expander("📁 Or Upload Video Instead", expanded=not has_video):
            video_upload = st.file_uploader("Upload video file (MP4, WebM, MOV)", type=["mp4", "webm", "mov"], key="live_upload_fallback")
            if video_upload:
                import hashlib
                buffer = video_upload.getbuffer()
                file_hash = hashlib.sha256(buffer).hexdigest()
                if st.session_state.get(f"media_hash_{person_id}") != file_hash:
                    st.session_state[f"media_source_{person_id}"] = "upload"
                    st.session_state[f"media_hash_{person_id}"] = file_hash
                    uploaded_path = os.path.join(VIDEO_DIR, f"performer_uploaded.mp4")
                    with open(uploaded_path, "wb") as f:
                        f.write(buffer)
                    st.session_state[video_path_key] = uploaded_path
                    st.session_state[f"audio_path_{person_id}"] = None
                    st.session_state[f"audio_bytes_{person_id}"] = None
                    st.session_state[transcript_key] = ""
                    st.session_state[f"_sync_transcript_{person_id}"] = True
                    st.session_state[f"story_data_{person_id}"] = None
                    st.session_state[f"speech_features_{person_id}"] = None
                    st.session_state[f"visual_features_{person_id}"] = None
                    st.session_state[f"evaluation_data_{person_id}"] = None
                    st.rerun()

        # Fallback Manual Transcript
        with st.expander("📝 Or Enter Transcript Manually", expanded=False):
            manual_text_input = st.text_area("Enter transcript text:", key="manual_transcript_live_fallback", height=100)
            if st.button("Save Manual Transcript", key="btn_save_manual_live"):
                if manual_text_input.strip():
                    st.session_state[transcript_key] = manual_text_input.strip()
                    st.session_state[f"_sync_transcript_{person_id}"] = True
                    st.session_state[f"story_data_{person_id}"] = None
                    st.session_state[f"evaluation_data_{person_id}"] = None
                    st.success("✅ Manual transcript saved.")
                    st.rerun()

        # Check if media or manual transcript is ready
        current_video = st.session_state.get(video_path_key)
        has_valid_video = bool(current_video and os.path.exists(current_video) and os.path.getsize(current_video) > 0)
        has_valid_transcript = bool((st.session_state.get(transcript_key) or "").strip())
        
        if has_valid_video or has_valid_transcript:
            st.markdown("---")
            st.subheader("🎬 Your Recording")
            
            c_v1, c_v2 = st.columns([1, 1])
            with c_v1:
                if has_valid_video:
                    st.video(current_video)
                else:
                    st.info("Transcript account ready for analysis.")
            with c_v2:
                textarea_key = f"textarea_{person_id}"
                if textarea_key not in st.session_state or st.session_state.get(f"_sync_transcript_{person_id}"):
                    st.session_state[textarea_key] = st.session_state.get(transcript_key, "")
                    st.session_state[f"_sync_transcript_{person_id}"] = False

                current_transcript = st.text_area("Transcript (auto-generated or enter manually):", height=130, key=textarea_key)
                if current_transcript != st.session_state.get(transcript_key):
                    st.session_state[transcript_key] = current_transcript or ""
                    st.session_state[f"story_data_{person_id}"] = None
                    st.session_state[f"evaluation_data_{person_id}"] = None

                st.write("")
                if st.button("▶️ Analyze Recording", type="primary", use_container_width=True):
                    run_pipeline(person_id, person_label)

            # Render full results
            st.markdown("---")
            render_individual_analysis(person_id, person_label)

            # Download Performance Report
            if st.session_state.get(f"evaluation_data_{person_id}") or st.session_state.get(f"speech_features_{person_id}") or st.session_state.get(f"visual_features_{person_id}"):
                st.markdown("---")
                st.header("📄 Performance Report")
                from services.report_generator import generate_performance_report
                score, breakdown = calculate_analysis_coverage(person_id)
                pdf_bytes = generate_performance_report(
                    person_label=person_label,
                    story=st.session_state.get(f"story_data_{person_id}"),
                    speech=st.session_state.get(f"speech_features_{person_id}"),
                    visual=st.session_state.get(f"visual_features_{person_id}"),
                    eval_data=st.session_state.get(f"evaluation_data_{person_id}"),
                    coverage_score=score,
                    coverage_breakdown=breakdown
                )
                st.download_button("📄 Download Performance Report (PDF)", data=pdf_bytes, file_name="TruthLens_Live_Performance_Report.pdf", mime="application/pdf", type="primary")

        elif not (ctx and getattr(ctx, "state", None) and ctx.state.playing):
            st.info("Record a live video above or upload a video file to begin analysis.")

    else:
        tab_a, tab_b = st.tabs(["Person A Analysis", "Person B Analysis"])
        with tab_a:
            render_person_panel("a", "Person A")
        with tab_b:
            render_person_panel("b", "Person B")

        st.markdown("---")
        st.header("⚖️ Compare & Assess")

        can_compare = bool(st.session_state.get("story_data_a")) and bool(st.session_state.get("story_data_b"))

        if not can_compare:
            st.info("💡 Analyze both Person A and Person B above to enable comparison.")
        else:
            if st.button("⚖️ Compare & Assess", type="primary", use_container_width=True):
                with st.spinner("Analyzing consistencies and conflicts..."):
                    try:
                        from services.story_comparator import compare_stories
                        res = compare_stories(st.session_state["story_data_a"], st.session_state["story_data_b"])
                        st.session_state["comparison_result"] = res
                    except Exception as e:
                        st.error(f"Comparison failed: {e}")

            if st.session_state.get("comparison_result"):
                render_comparison(st.session_state["comparison_result"], "Person A", "Person B")

        st.markdown("---")
        st.header("📄 Download Comparison Report")
        from services.report_generator import generate_evidence_report
        if st.session_state.get("comparison_result"):
            pdf_bytes = generate_evidence_report(
                st.session_state["comparison_result"],
                story_a=st.session_state.get("story_data_a"),
                story_b=st.session_state.get("story_data_b"),
                speech_a=st.session_state.get("speech_features_a"),
                speech_b=st.session_state.get("speech_features_b"),
                visual_a=st.session_state.get("visual_features_a"),
                visual_b=st.session_state.get("visual_features_b")
            )
            st.download_button("📄 Download Evidence Report (PDF)", data=pdf_bytes, file_name="TruthLens_Report.pdf", mime="application/pdf", type="primary")
        else:
            st.info("Run the comparison to generate the downloadable report.")


if __name__ == "__main__":
    main()
