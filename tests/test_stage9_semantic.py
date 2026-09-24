import os
import sys
import unittest

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from services.story_comparator import _normalize_for_match

class TestSemantic(unittest.TestCase):
    def test_normalization(self):
        self.assertEqual(_normalize_for_match("about 10 minutes"), _normalize_for_match("roughly ten minutes"))
        self.assertEqual(_normalize_for_match("9 AM"), _normalize_for_match("around 9 AM"))
        self.assertEqual(_normalize_for_match("cafeteria"), _normalize_for_match("canteen"))
        self.assertEqual(_normalize_for_match("met Rahul"), _normalize_for_match("spoke with Rahul"))
        
        self.assertNotEqual(_normalize_for_match("library"), _normalize_for_match("canteen"))
        self.assertNotEqual(_normalize_for_match("9 AM"), _normalize_for_match("2 PM"))

if __name__ == "__main__":
    unittest.main()
