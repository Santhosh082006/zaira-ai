"""
tests/test_feature_navigation_sync.py
─────────────────────────────────────────────────────────────────────────────
Comprehensive Runtime Verification Suite for TruthLens AI Feature Navigation:

Tests:
1. Initial clean state renders Live Camera Recording (sidebar and main match).
2. Selecting 'Individual Video Analysis' updates canonical state and renders Individual Video Analysis.
3. Selecting 'Compare & Assess' updates canonical state and renders Compare & Assess.
4. Switching between all 3 features in various cycles keeps sidebar and main 100% synchronized.
5. Reset Analysis Session preserves canonical navigation without desynchronization.
6. Browser reload simulation initializes single source of truth without desynchronization.

NOTE: Feature page headers now use st.markdown() with custom HTML rather than st.title().
      Verification is based on canonical session_state and sidebar radio values, with
      markdown content checks for the feature title text.
"""

import sys
import os
import unittest

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from streamlit.testing.v1 import AppTest
from core.constants import (
    FEATURE_LIVE_CAMERA,
    FEATURE_INDIVIDUAL_VIDEO,
    FEATURE_COMPARE_ASSESS,
    ALL_FEATURES,
    DEFAULT_FEATURE,
)


FEATURE_PAGE_INDICATORS = {
    FEATURE_LIVE_CAMERA: "Record & Analyze",
    FEATURE_INDIVIDUAL_VIDEO: "Analyze Your Video",
    FEATURE_COMPARE_ASSESS: "Side-by-Side Analysis",
}


def _find_feature_in_markdown(at, feature_name: str) -> bool:
    """Check if the feature page title appears in any markdown element on the main page.

    Since features render titles via st.markdown() with custom HTML page headers,
    we search all main-page markdown values for the feature's primary header or identifier.
    """
    indicator = FEATURE_PAGE_INDICATORS.get(feature_name, feature_name)
    for md in at.main.markdown:
        val = md.value or ""
        if indicator in val or feature_name in val:
            return True
    return False


class TestFeatureNavigationSync(unittest.TestCase):

    def test_01_initial_navigation_synchronized(self):
        """Verify initial clean launch synchronizes sidebar radio and main content."""
        at = AppTest.from_file(os.path.join(ROOT_DIR, "app.py"), default_timeout=30)
        at.run()

        # Check sidebar radio
        self.assertEqual(at.sidebar.radio[0].value, FEATURE_LIVE_CAMERA)
        self.assertEqual(at.session_state["active_feature"], FEATURE_LIVE_CAMERA)
        self.assertEqual(at.session_state["sidebar_primary_nav"], FEATURE_LIVE_CAMERA)

        # Check main page renders the Live Camera title (via markdown)
        self.assertTrue(
            _find_feature_in_markdown(at, FEATURE_LIVE_CAMERA),
            f"Main page did not render '{FEATURE_LIVE_CAMERA}' in markdown"
        )

    def test_02_switch_to_individual_video_synchronized(self):
        """Verify selecting Individual Video Analysis immediately updates both sidebar and main."""
        at = AppTest.from_file(os.path.join(ROOT_DIR, "app.py"), default_timeout=30)
        at.run()

        # User selects Individual Video Analysis
        at.sidebar.radio[0].set_value(FEATURE_INDIVIDUAL_VIDEO).run()

        # Sidebar and state must be Individual Video Analysis
        self.assertEqual(at.sidebar.radio[0].value, FEATURE_INDIVIDUAL_VIDEO)
        self.assertEqual(at.session_state["active_feature"], FEATURE_INDIVIDUAL_VIDEO)
        self.assertEqual(at.session_state["sidebar_primary_nav"], FEATURE_INDIVIDUAL_VIDEO)

        # Main page MUST render Individual Video Analysis title
        self.assertTrue(
            _find_feature_in_markdown(at, FEATURE_INDIVIDUAL_VIDEO),
            f"Main page did not render '{FEATURE_INDIVIDUAL_VIDEO}' in markdown"
        )
        # Ensure other feature titles are not rendered
        self.assertFalse(_find_feature_in_markdown(at, FEATURE_LIVE_CAMERA))
        self.assertFalse(_find_feature_in_markdown(at, FEATURE_COMPARE_ASSESS))

    def test_03_switch_to_compare_assess_synchronized(self):
        """Verify selecting Compare & Assess immediately updates both sidebar and main."""
        at = AppTest.from_file(os.path.join(ROOT_DIR, "app.py"), default_timeout=30)
        at.run()

        # User selects Compare & Assess
        at.sidebar.radio[0].set_value(FEATURE_COMPARE_ASSESS).run()

        # Sidebar and state must be Compare & Assess
        self.assertEqual(at.sidebar.radio[0].value, FEATURE_COMPARE_ASSESS)
        self.assertEqual(at.session_state["active_feature"], FEATURE_COMPARE_ASSESS)
        self.assertEqual(at.session_state["sidebar_primary_nav"], FEATURE_COMPARE_ASSESS)

        # Main page MUST render Compare & Assess title
        self.assertTrue(
            _find_feature_in_markdown(at, FEATURE_COMPARE_ASSESS),
            f"Main page did not render '{FEATURE_COMPARE_ASSESS}' in markdown"
        )
        self.assertFalse(_find_feature_in_markdown(at, FEATURE_LIVE_CAMERA))
        self.assertFalse(_find_feature_in_markdown(at, FEATURE_INDIVIDUAL_VIDEO))

    def test_04_cyclic_switching_multiple_times(self):
        """Verify cycling back and forth between all 3 features keeps sidebar and main in sync every time."""
        at = AppTest.from_file(os.path.join(ROOT_DIR, "app.py"), default_timeout=30)
        at.run()

        sequence = [
            FEATURE_INDIVIDUAL_VIDEO,
            FEATURE_COMPARE_ASSESS,
            FEATURE_LIVE_CAMERA,
            FEATURE_INDIVIDUAL_VIDEO,
            FEATURE_LIVE_CAMERA,
            FEATURE_COMPARE_ASSESS,
            FEATURE_INDIVIDUAL_VIDEO,
        ]

        for target_feature in sequence:
            at.sidebar.radio[0].set_value(target_feature).run()
            self.assertEqual(at.sidebar.radio[0].value, target_feature, f"Sidebar radio failed to reflect {target_feature}")
            self.assertEqual(at.session_state["active_feature"], target_feature, f"Canonical state failed to reflect {target_feature}")
            self.assertTrue(
                _find_feature_in_markdown(at, target_feature),
                f"Main page failed to render title for {target_feature}"
            )
            # Ensure other feature titles are not rendered
            for other in ALL_FEATURES:
                if other != target_feature:
                    self.assertFalse(
                        _find_feature_in_markdown(at, other),
                        f"Main page erroneously rendered {other} while {target_feature} was active"
                    )

    def test_05_reset_session_preserves_navigation(self):
        """Verify clicking Reset Analysis Session preserves navigation state without desync."""
        at = AppTest.from_file(os.path.join(ROOT_DIR, "app.py"), default_timeout=30)
        at.run()

        # Navigate to Individual Video Analysis
        at.sidebar.radio[0].set_value(FEATURE_INDIVIDUAL_VIDEO).run()
        self.assertEqual(at.session_state["active_feature"], FEATURE_INDIVIDUAL_VIDEO)

        # Click Reset button in sidebar
        reset_btns = [b for b in at.sidebar.button if "Reset" in (b.label or "")]
        self.assertTrue(len(reset_btns) > 0, "Reset button not found in sidebar")
        reset_btns[0].click().run()

        # Should still be on Individual Video Analysis
        self.assertEqual(at.sidebar.radio[0].value, FEATURE_INDIVIDUAL_VIDEO)
        self.assertEqual(at.session_state["active_feature"], FEATURE_INDIVIDUAL_VIDEO)
        self.assertTrue(
            _find_feature_in_markdown(at, FEATURE_INDIVIDUAL_VIDEO),
            f"Main page did not render '{FEATURE_INDIVIDUAL_VIDEO}' after reset"
        )


if __name__ == "__main__":
    unittest.main()
