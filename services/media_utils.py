import os
import subprocess

def extract_audio_from_video(video_path: str, output_path: str) -> bool:
    """
    Extracts the audio track from a video file using FFmpeg and saves it as a WAV file.
    Returns True if successful, False otherwise.
    """
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Video file not found: {video_path}")

    try:
        # -y : overwrite output file if it exists
        # -vn : no video
        # -acodec pcm_s16le : WAV format
        # -ar 16000 : 16kHz sampling rate (good for Whisper)
        # -ac 1 : mono
        cmd = [
            "ffmpeg",
            "-y",
            "-i", video_path,
            "-vn",
            "-acodec", "pcm_s16le",
            "-ar", "16000",
            "-ac", "1",
            output_path
        ]
        
        # Run ffmpeg, suppress stdout/stderr unless it fails
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False
        )
        
        if result.returncode != 0:
            # Check if it's because there's no audio stream
            if "does not contain any stream" in result.stderr or "Output file is empty" in result.stderr:
                raise ValueError("Video does not contain an audio track.")
            raise RuntimeError(f"FFmpeg extraction failed: {result.stderr}")
            
        if not os.path.exists(output_path):
            raise RuntimeError("FFmpeg extraction succeeded but output file is missing.")
            
        return True

    except FileNotFoundError:
        # ffmpeg is not installed or not in PATH
        raise RuntimeError("FFmpeg is missing. Please install FFmpeg on your system to process video audio.")
    except Exception as e:
        raise e
