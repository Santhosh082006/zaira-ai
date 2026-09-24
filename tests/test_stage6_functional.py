import os
import sys
import wave
import numpy as np

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Ensure root dir is in path
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from services.speech_features import extract_speech_features

def create_test_wav(filepath: str, duration_sec: float, silence: bool = False):
    """Creates a temporary WAV file for testing."""
    sample_rate = 16000
    n_samples = int(duration_sec * sample_rate)
    
    if silence:
        data = np.zeros(n_samples, dtype=np.int16)
    else:
        # Create a simple 200 Hz sine wave for "speech" simulation
        t = np.linspace(0, duration_sec, n_samples, False)
        # Adding some amplitude modulation to simulate pauses/speaking
        modulation = np.sin(2 * np.pi * 0.5 * t)
        data = np.sin(2 * np.pi * 200 * t) * 10000 * (modulation > 0)
        data = data.astype(np.int16)
        
    with wave.open(filepath, 'w') as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(sample_rate)
        f.writeframes(data.tobytes())

def test_speech_features():
    print("==================================================================")
    print("  TruthLens AI — Stage 6 Speech Features Test")
    print("==================================================================")
    
    test_audio_path = "test_audio_temp.wav"
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
        # Test 1: Valid audio
        create_test_wav(test_audio_path, 3.0, silence=False)
        transcript = "um well I went to the library um"
        res = extract_speech_features(test_audio_path, transcript)
        
        assert_test(res["reliability_flag"] in ["good", "pitch_unreliable"], "Valid audio runs without error")
        if res["duration_seconds"] is None:
            print("ERROR: res is", res)
        assert_test(res["word_count"] == 8, "Word count correctly ignores punctuation")
        assert_test(res["filler_word_count"] == 2, "Filler words (um) correctly counted")
        assert_test(res["duration_seconds"] > 2.9, "Duration correctly calculated")
        assert_test(res["speaking_rate_wpm"] > 100, "WPM calculated")
        assert_test(res["energy_mean_db"] is not None, "Energy calculated")
        
        # Test 2: Silence
        create_test_wav(test_audio_path, 2.0, silence=True)
        res = extract_speech_features(test_audio_path, transcript)
        assert_test(res["reliability_flag"] in ["all_silence", "pitch_unreliable"], "Silence handled without crashing")
        assert_test(res["pause_count"] == 1, "Silence reports 1 pause covering full duration")
        
        # Test 3: Very short audio
        create_test_wav(test_audio_path, 0.2, silence=False)
        res = extract_speech_features(test_audio_path, "short")
        assert_test(res["reliability_flag"] == "audio_too_short", "Short audio caught by reliability flag")
        assert_test(res["pitch_mean_hz"] is None, "Pitch is None for very short audio")
        
        # Test 4: Missing file
        res = extract_speech_features("does_not_exist.wav", "test")
        assert_test(res["reliability_flag"] == "audio_missing", "Missing audio handled safely")
        
        # Test 5: Empty transcript
        create_test_wav(test_audio_path, 2.0, silence=False)
        res = extract_speech_features(test_audio_path, "")
        assert_test(res["word_count"] == 0, "Empty transcript word count = 0")
        assert_test(res["speaking_rate_wpm"] == 0.0, "Empty transcript WPM = 0.0")
        assert_test(res["filler_word_count"] == 0, "Empty transcript filler count = 0")

    finally:
        if os.path.exists(test_audio_path):
            os.remove(test_audio_path)

    print("==================================================================")
    print(f"  Tests run    : {total}")
    print(f"  Passed       : {passed}")
    print(f"  Failed       : {total - passed}")
    print("==================================================================")
    
    if passed < total:
        sys.exit(1)

if __name__ == "__main__":
    test_speech_features()
