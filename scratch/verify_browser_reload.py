"""
scratch/verify_browser_reload.py
─────────────────────────────────────────────────────────────────────────────
Comprehensive Acceptance Suite for TruthLens Three-Feature Architecture:
1. Live Camera Recording (record/sample -> analyze -> individual results)
2. Individual Video Analysis (upload/sample -> analyze -> individual results, no video B needed)
3. Compare & Assess (Video A + Video B -> independent analyses -> comparison)
4. State Isolation: Individual Video Analysis does NOT contaminate Compare & Assess
5. State Isolation: Compare & Assess does NOT contaminate Individual Video Analysis
6. Browser Reload: starts completely fresh across all three features
7. Reset Analysis Session: clears active session manually
"""

import sys
import os
import unittest
import shutil

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from streamlit.testing.v1 import AppTest
from core.constants import VIDEO_DIR
from unittest.mock import patch


def _mock_speech_features(audio_path, transcript=""):
    return {
        "duration_seconds": 15.0,
        "word_count": 35,
        "speaking_rate_wpm": 140.0,
        "pause_count": 2,
        "total_pause_duration_sec": 1.5,
        "filler_word_count": 0,
        "reliability_flag": "good"
    }


def _mock_visual_features(video_path):
    return {
        "face_detected": True,
        "face_presence_ratio": 0.95,
        "head_movement_count": 6,
        "head_movement_rate_per_min": 24.0,
        "blink_count": 5,
        "duration_seconds": 15.0,
        "tracking_reliability": "good"
    }


def _mock_transcribe(*args, **kwargs):
    return "I arrived at the headquarters to present our quarterly roadmap and lead the team."


def _mock_demux(video_path, output_audio_path=None):
    if output_audio_path:
        os.makedirs(os.path.dirname(os.path.abspath(output_audio_path)), exist_ok=True)
        with open(output_audio_path, "wb") as f:
            f.write(b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00\x44\xac\x00\x00\x88\x58\x01\x00\x02\x00\x10\x00data\x00\x00\x00\x00")
        return True, None
    return True, None


def _mock_story_facts(transcript="", person_name=""):
    return {
        "person": person_name,
        "summary": "Account summary",
        "extraction_confidence": "high",
        "events": [
            {
                "event_id": 1,
                "sequence": 1,
                "time": "9:00 AM",
                "location": "Headquarters",
                "description": "Presented quarterly roadmap",
                "source_text": transcript
            }
        ],
        "claims": [
            {
                "claim_id": 1,
                "subject": "Roadmap",
                "attribute": "presented",
                "value": "Team",
                "source_text": transcript
            }
        ],
        "all_people_mentioned": ["Team"],
        "all_locations_mentioned": ["Headquarters"],
        "all_times_mentioned": ["9:00 AM"],
        "all_dates_mentioned": []
    }


@patch("processors.ingestion.video_demuxer.demux_video_to_audio", side_effect=_mock_demux)
@patch("services.story_analyzer.extract_story_facts", side_effect=_mock_story_facts)
@patch("app.get_whisper_model", return_value="mock_model")
@patch("services.llm_provider.call_llm", side_effect=RuntimeError("Offline test mode"))
@patch("services.visual_features.extract_visual_features", side_effect=_mock_visual_features)
@patch("services.speech_features.extract_speech_features", side_effect=_mock_speech_features)
@patch("services.speech_to_text.transcribe_audio", side_effect=_mock_transcribe)
def test_three_features_and_session_lifecycle(mock_trans, mock_spk, mock_vis, mock_llm, mock_whisper, mock_story, mock_demux):
    print("=" * 70)
    print("RUNNING COMPLETE ACCEPTANCE SUITE: THREE FEATURES & SESSION ISOLATION")
    print("=" * 70)

    # ─────────────────────────────────────────────────────────────────────────
    # ACCEPTANCE TEST 1: Initial Fresh Browser Session & Exactly 3 Primary Features
    # ─────────────────────────────────────────────────────────────────────────
    print("\n--- TEST 1: Fresh Session & Exactly 3 Sidebar Navigation Options ---")
    at1 = AppTest.from_file(os.path.join(ROOT_DIR, "app.py"), default_timeout=60).run()
    assert not at1.exception, f"App crashed on startup: {at1.exception}"

    # Radio must show strictly the three primary features
    radios = at1.sidebar.radio[0].proto.options
    print(f"Sidebar radio options: {radios}")
    expected_options = [
        "🎥 Live Camera Recording",
        "📁 Individual Video Analysis",
        "⚖️ Compare & Assess"
    ]
    assert list(radios) == expected_options, f"Expected {expected_options}, got {list(radios)}"
    assert at1.sidebar.radio[0].value == "🎥 Live Camera Recording"

    # Initial Live Camera view is clean
    titles = [t.value for t in at1.title]
    print(f"Initial Page title: {titles}")
    assert any("🎥 Live Camera Recording" in t for t in titles)

    # No analyze buttons, no previous videos in session state
    analyze_btns = [b for b in at1.button if "Analyze Performance" in b.label]
    assert len(analyze_btns) == 0, f"Expected 0 analyze buttons in fresh session, found {len(analyze_btns)}"
    assert at1.session_state["video_path_live"] is None
    assert at1.session_state["evaluation_data_live"] is None
    assert at1.session_state["video_path_upload"] is None
    assert at1.session_state["evaluation_data_upload"] is None
    assert at1.session_state["video_path_a"] is None
    assert at1.session_state["video_path_b"] is None
    assert at1.session_state["multimodal_comparison"] is None
    print("✓ TEST 1 PASSED: Fresh session has exactly 3 primary features and completely clean state.")

    # ─────────────────────────────────────────────────────────────────────────
    # ACCEPTANCE TEST 2: Live Camera Recording -> record/sample -> analyze
    # ─────────────────────────────────────────────────────────────────────────
    print("\n--- TEST 2: Live Camera Workflow ---")
    initial_session_id = at1.session_state["_session_id"]
    # Load sample into live camera
    load_live_btn = [b for b in at1.button if "Use Sample Video for Live Camera" in b.label][0]
    load_live_btn.click().run()
    assert not at1.exception
    assert at1.session_state["video_path_live"] is not None
    assert os.path.exists(at1.session_state["video_path_live"])

    # Analyze button now appears
    analyze_live_btn = [b for b in at1.button if "Analyze Performance" in b.label]
    assert len(analyze_live_btn) >= 1
    # Run analysis
    analyze_live_btn[0].click().run()
    assert not at1.exception
    assert at1.session_state["evaluation_data_live"] is not None
    assert at1.session_state["speech_features_live"] is not None
    assert at1.session_state["visual_features_live"] is not None
    print("✓ TEST 2 PASSED: Live Camera workflow successfully completed individual analysis.")

    # ─────────────────────────────────────────────────────────────────────────
    # ACCEPTANCE TEST 3: Individual Video Analysis -> Upload ONE video -> Analyze
    # ─────────────────────────────────────────────────────────────────────────
    print("\n--- TEST 3: Individual Video Analysis Workflow ---")
    at_ind = AppTest.from_file(os.path.join(ROOT_DIR, "app.py"), default_timeout=60).run()
    at_ind.sidebar.radio[0].set_value("📁 Individual Video Analysis").run()
    assert not at_ind.exception
    titles = [t.value for t in at_ind.title]
    assert any("📁 Individual Video Analysis" in t for t in titles)

    # Initially empty
    assert at_ind.session_state["video_path_upload"] is None
    assert at_ind.session_state["evaluation_data_upload"] is None

    # Load test video for individual analysis
    load_ind_btn = [b for b in at_ind.button if "Load Selected Video" in b.label][0]
    load_ind_btn.click().run()
    assert not at_ind.exception
    assert at_ind.session_state["video_path_upload"] is not None
    assert os.path.exists(at_ind.session_state["video_path_upload"])

    # Analyze button appears
    analyze_ind_btn = [b for b in at_ind.button if "Analyze Performance" in b.label]
    assert len(analyze_ind_btn) >= 1
    analyze_ind_btn[0].click().run()
    assert not at_ind.exception
    assert at_ind.session_state["evaluation_data_upload"] is not None
    assert at_ind.session_state["speech_features_upload"] is not None
    assert at_ind.session_state["visual_features_upload"] is not None

    # Crucial check: Video B is NEVER required or touched!
    assert at_ind.session_state["video_path_b"] is None
    assert at_ind.session_state["evaluation_data_b"] is None
    print("✓ TEST 3 PASSED: Individual Video Analysis analyzed ONE video without requiring Video B.")

    # ─────────────────────────────────────────────────────────────────────────
    # ACCEPTANCE TEST 4: State Isolation between Individual Video and Compare
    # ─────────────────────────────────────────────────────────────────────────
    print("\n--- TEST 4: Individual Video Isolation (Switch to Compare & Assess) ---")
    # In at_ind (where Individual Video is analyzed), switch to Compare & Assess
    at_ind.sidebar.radio[0].set_value("⚖️ Compare & Assess").run()
    assert not at_ind.exception

    # Compare & Assess must NOT automatically adopt the individual video!
    assert at_ind.session_state["video_path_a"] is None, "Video A must start empty in Compare"
    assert at_ind.session_state["video_path_b"] is None, "Video B must start empty in Compare"
    assert at_ind.session_state["multimodal_comparison"] is None, "Comparison must start empty"
    print("✓ TEST 4 PASSED: Compare & Assess is completely isolated from Individual Video.")

    # ─────────────────────────────────────────────────────────────────────────
    # ACCEPTANCE TEST 5: Compare & Assess Workflow (Video A + B -> Independent -> Comparison)
    # ─────────────────────────────────────────────────────────────────────────
    print("\n--- TEST 5: Compare & Assess Workflow ---")
    at_comp = AppTest.from_file(os.path.join(ROOT_DIR, "app.py"), default_timeout=60).run()
    at_comp.sidebar.radio[0].set_value("⚖️ Compare & Assess").run()
    assert not at_comp.exception

    # Load Video A
    load_a = [b for b in at_comp.button if "Use Sample Video A" in b.label][0]
    load_a.click().run()
    assert not at_comp.exception
    assert at_comp.session_state["video_path_a"] is not None
    assert at_comp.session_state["video_path_b"] is None

    # Load Video B
    load_b = [b for b in at_comp.button if "Use Sample Video B" in b.label][0]
    load_b.click().run()
    assert not at_comp.exception
    assert at_comp.session_state["video_path_b"] is not None

    # Click Analyze & Compare
    comp_exec_btn = [b for b in at_comp.button if "Analyze & Compare" in b.label or "Compare Measured Performance" in b.label][0]
    comp_exec_btn.click().run()
    assert not at_comp.exception

    # Independent analyses for both A and B must exist!
    assert at_comp.session_state["evaluation_data_a"] is not None, "Independent Analysis A must be computed"
    assert at_comp.session_state["evaluation_data_b"] is not None, "Independent Analysis B must be computed"
    assert at_comp.session_state["multimodal_comparison"] is not None, "Comparative analysis must be computed"
    print("✓ TEST 5 PASSED: Compare & Assess successfully performed independent analyses and comparative result.")

    # ─────────────────────────────────────────────────────────────────────────
    # ACCEPTANCE TEST 6: Comparison Isolation (Switch from Compare to Individual)
    # ─────────────────────────────────────────────────────────────────────────
    print("\n--- TEST 6: Comparison Isolation (Switch to Individual Video Analysis) ---")
    at_comp.sidebar.radio[0].set_value("📁 Individual Video Analysis").run()
    assert not at_comp.exception

    # Individual Video must NOT automatically adopt Video A or B!
    assert at_comp.session_state["video_path_upload"] is None, "Individual video must start empty"
    assert at_comp.session_state["evaluation_data_upload"] is None, "Individual analysis must start empty"
    print("✓ TEST 6 PASSED: Individual Video Analysis is completely isolated from Compare & Assess.")

    # ─────────────────────────────────────────────────────────────────────────
    # ACCEPTANCE TEST 7: Browser Reload Starts Fresh Across All 3 Workflows
    # ─────────────────────────────────────────────────────────────────────────
    print("\n--- TEST 7: Browser Reload Starts Clean Across All Features ---")
    at_fresh = AppTest.from_file(os.path.join(ROOT_DIR, "app.py"), default_timeout=60).run()
    assert not at_fresh.exception
    # Check all slots
    assert at_fresh.session_state["video_path_live"] is None
    assert at_fresh.session_state["video_path_upload"] is None
    assert at_fresh.session_state["video_path_a"] is None
    assert at_fresh.session_state["video_path_b"] is None
    assert at_fresh.session_state["evaluation_data_live"] is None
    assert at_fresh.session_state["evaluation_data_upload"] is None
    assert at_fresh.session_state["evaluation_data_a"] is None
    assert at_fresh.session_state["evaluation_data_b"] is None
    assert at_fresh.session_state["multimodal_comparison"] is None
    print("✓ TEST 7 PASSED: Browser reload starts completely fresh across all 3 features.")

    # ─────────────────────────────────────────────────────────────────────────
    # ACCEPTANCE TEST 8: Manual Reset Button
    # ─────────────────────────────────────────────────────────────────────────
    print("\n--- TEST 8: Manual Reset Button ---")
    reset_btn = [b for b in at_comp.sidebar.button if "Reset Analysis Session" in b.label][0]
    reset_btn.click().run()
    assert not at_comp.exception
    assert at_comp.session_state["video_path_a"] is None
    assert at_comp.session_state["video_path_b"] is None
    assert at_comp.session_state["video_path_upload"] is None
    assert at_comp.session_state["video_path_live"] is None
    print("✓ TEST 8 PASSED: Manual Reset button successfully clears all feature states.")

    print("\n" + "=" * 70)
    print("ALL 8 ACCEPTANCE TESTS PASSED SUCCESSFULLY!")
    print("=" * 70)


if __name__ == "__main__":
    test_three_features_and_session_lifecycle()
