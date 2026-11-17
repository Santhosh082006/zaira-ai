import os
import sys
import shutil
import subprocess

def ensure_ffmpeg_in_path() -> str:
    """
    Ensures that an executable named 'ffmpeg' is accessible in PATH.
    Discovers imageio_ffmpeg, creates standard 'ffmpeg.exe' aliases in known
    script/bin directories if missing, and prepends the directory to os.environ['PATH'].
    """
    try:
        import imageio_ffmpeg
        exe = imageio_ffmpeg.get_ffmpeg_exe()
        if exe and os.path.exists(exe):
            exe_dir = os.path.dirname(exe)
            std_ffmpeg = os.path.join(exe_dir, "ffmpeg.exe" if sys.platform == "win32" else "ffmpeg")
            if not os.path.exists(std_ffmpeg):
                try:
                    shutil.copyfile(exe, std_ffmpeg)
                except Exception:
                    pass

            scripts_dir = os.path.dirname(os.path.abspath(sys.executable))
            venv_ffmpeg = os.path.join(scripts_dir, "ffmpeg.exe" if sys.platform == "win32" else "ffmpeg")
            if not os.path.exists(venv_ffmpeg):
                try:
                    shutil.copyfile(exe, venv_ffmpeg)
                except Exception:
                    pass

            current_path = os.environ.get("PATH", "")
            path_dirs = set(current_path.split(os.pathsep))
            for d in [scripts_dir, exe_dir]:
                if d and d not in path_dirs:
                    os.environ["PATH"] = d + os.pathsep + os.environ.get("PATH", "")
                    path_dirs.add(d)

            return std_ffmpeg if os.path.exists(std_ffmpeg) else exe
    except Exception:
        pass
    return "ffmpeg"

# Automatically ensure ffmpeg is configured on module load
ensure_ffmpeg_in_path()

def get_ffmpeg_binary() -> str:
    """
    Locates an available ffmpeg binary.
    Prioritizes imageio_ffmpeg (self-contained python wheel) if installed,
    otherwise falls back to system 'ffmpeg'.
    """
    return ensure_ffmpeg_in_path()

def extract_audio_from_video(video_path: str, output_path: str) -> bool:
    """
    Extracts the audio track from a video file using FFmpeg and saves it as a WAV file.
    Returns True if successful, False otherwise.
    """
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Video file not found: {video_path}")

    ffmpeg_exe = get_ffmpeg_binary()

    try:
        # -y : overwrite output file if it exists
        # -vn : no video
        # -acodec pcm_s16le : WAV format
        # -ar 16000 : 16kHz sampling rate (good for Whisper)
        # -ac 1 : mono
        cmd = [
            ffmpeg_exe,
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
        raise RuntimeError(
            "FFmpeg is missing. Install imageio-ffmpeg ('pip install imageio-ffmpeg') "
            "or install FFmpeg on your system to process video audio."
        )
    except Exception as e:
        raise e
