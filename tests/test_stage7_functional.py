import os
import sys
import numpy as np
import cv2

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from services.visual_features import extract_visual_features

def create_mock_video(filepath: str, frames: int, has_face: bool = False):
    """Creates a temporary MP4 video for testing using OpenCV."""
    height, width = 240, 320
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(filepath, fourcc, 30.0, (width, height))
    
    for i in range(frames):
        frame = np.zeros((height, width, 3), dtype=np.uint8)
        if has_face:
            # We can't easily mock a realistic face that MediaPipe will detect
            # without including an actual image file.
            # We'll just draw a circle, though MediaPipe won't recognize it as a face.
            # This is fine, we just expect face_detected=False for pure synthetic circles.
            cv2.circle(frame, (width//2, height//2), 50, (200, 200, 200), -1)
        out.write(frame)
        
    out.release()

def test_visual_features():
    print("==================================================================")
    print("  TruthLens AI — Stage 7 Visual Features Test")
    print("==================================================================")
    
    test_video_path = "test_video_temp.mp4"
    passed = 0
    total = 0
    
    def assert_test(condition, name):
        nonlocal passed, total
        total += 1
        if condition:
            print(f"  PASS  {name}")
            passed += 1
        else:
            print(f"  FAIL  {name}")
            
    try:
        # Test 1: Missing video
        res = extract_visual_features("does_not_exist.mp4")
        assert_test(res["tracking_reliability"] == "video_missing", "Missing video handled safely")
        
        # Test 2: Unreadable/corrupt video (create an empty file)
        with open(test_video_path, "w") as f:
            f.write("not a video")
        res = extract_visual_features(test_video_path)
        assert_test(res["tracking_reliability"] in ["video_unreadable", "video_empty"], "Corrupt video handled safely")
        
        # Test 3: Valid video but no actual human face (mocked)
        create_mock_video(test_video_path, 30, has_face=False)
        res = extract_visual_features(test_video_path)
        assert_test(res["face_detected"] is False, "No-face video correctly identifies absence of face")
        assert_test(res["face_presence_ratio"] == 0.0, "Face presence ratio is 0.0")
        assert_test(res["blink_count"] is None, "Blinks are None when no face")
        assert_test(res["tracking_reliability"] == "no_face_found", "Tracking reliability set to no_face_found")

        # Test 4: Schema validation
        assert_test("head_movement_count" in res, "Schema contains head_movement_count")
        assert_test("blink_count" in res, "Schema contains blink_count")

        # Test 5: Unexpected error handling
        import unittest.mock
        with open(test_video_path, "w") as f:
            f.write("mock") # Just to make the file exist
        with unittest.mock.patch('services.visual_features.cv2.VideoCapture') as mock_cap:
            mock_cap.return_value.isOpened.return_value = True
            mock_cap.return_value.get.return_value = 100
            mock_cap.return_value.read.side_effect = RuntimeError("Mocked crash inside processing loop")
            res_error = extract_visual_features(test_video_path)
            assert_test(res_error["tracking_reliability"] == "analysis_error", "Unexpected error safely caught")
            assert_test(res_error["face_detected"] is None, "Fallback schema retains None for failed features")

    finally:
        if os.path.exists(test_video_path):
            os.remove(test_video_path)

    print("==================================================================")
    print(f"  Tests run    : {total}")
    print(f"  Passed       : {passed}")
    print(f"  Failed       : {total - passed}")
    print("==================================================================")
    
    if passed < total:
        sys.exit(1)

if __name__ == "__main__":
    test_visual_features()
