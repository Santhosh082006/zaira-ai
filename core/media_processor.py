import os
import uuid
import tempfile
import librosa
from typing import Optional
from core.schemas import MediaAnalysisResult
from core.constants import AUDIO_DIR

from services.speech_to_text import load_whisper_model, transcribe_audio
from services.speech_features import extract_speech_features
from services.visual_features import extract_visual_features
from processors.ingestion.video_demuxer import demux_video_to_audio

class MediaProcessor:
    def __init__(self, mock_transcription: bool = False):
        self.mock_transcription = mock_transcription
        self._whisper_model = None
        
        # Ensure audio dir exists for temporary demuxed files
        os.makedirs(AUDIO_DIR, exist_ok=True)

    def _get_whisper_model(self):
        if self._whisper_model is None and not self.mock_transcription:
            # Load model explicitly. If it fails, raise the exception. No silent fallback.
            self._whisper_model = load_whisper_model()
        return self._whisper_model

    def _get_audio_duration(self, audio_path: str) -> float:
        try:
            y, sr = librosa.load(audio_path, sr=None)
            return float(librosa.get_duration(y=y, sr=sr))
        except Exception:
            return 0.0

    def _normalize_audio(self, audio_path: str) -> str:
        import subprocess
        out_fd, out_path = tempfile.mkstemp(suffix=".wav", dir=AUDIO_DIR)
        os.close(out_fd)
        
        cmd = [
            "ffmpeg", "-y", "-i", audio_path,
            "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le",
            out_path
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        except subprocess.CalledProcessError as e:
            if os.path.exists(out_path):
                os.remove(out_path)
            raise ValueError(f"FFmpeg normalization failed: {e.stderr}")
            
        return out_path

    def process_audio(self, audio_path: str) -> MediaAnalysisResult:
        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"Audio file not found: {audio_path}")
            
        normalized_path = None
        try:
            # Normalize WebM/Opus or any audio format to WAV for librosa compatibility
            normalized_path = self._normalize_audio(audio_path)
            
            duration = self._get_audio_duration(normalized_path)
            
            # 1. Transcription
            if self.mock_transcription:
                transcript = "This is a deterministic mocked transcript. I solved the problem very well and communicated clearly."
            else:
                model = self._get_whisper_model()
                transcript_raw = transcribe_audio(model, normalized_path)
                transcript = (transcript_raw.get("text", "") if isinstance(transcript_raw, dict) else str(transcript_raw or "")).strip()
                    
            # 2. Speech Analysis
            speech_metrics = None
            if not self.mock_transcription:
                try:
                    speech_metrics = extract_speech_features(normalized_path, transcript)
                except Exception:
                    pass

            # 3. Content Analysis
            content_analysis = {}

            return MediaAnalysisResult(
                transcript=transcript,
                duration=duration,
                speech_metrics=speech_metrics,
                content_analysis=content_analysis,
                media_reference=audio_path
            )
        finally:
            if normalized_path and os.path.exists(normalized_path):
                try:
                    os.remove(normalized_path)
                except Exception:
                    pass

    def process_video(self, video_path: str) -> MediaAnalysisResult:
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"Video file not found: {video_path}")
            
        # 1. Demux Audio
        session_id = uuid.uuid4().hex[:8]
        audio_path = os.path.join(AUDIO_DIR, f"demux_{session_id}.wav")
        
        try:
            success, err = demux_video_to_audio(video_path, audio_path)
            if not success or not os.path.exists(audio_path):
                raise RuntimeError(f"Video audio extraction failed: {err}")
                
            audio_result = self.process_audio(audio_path)
            duration = audio_result.duration
            transcript = audio_result.transcript
            speech_metrics = audio_result.speech_metrics
            content_analysis = audio_result.content_analysis
        finally:
            # Ensure temporary audio file is always cleaned up
            if os.path.exists(audio_path):
                try:
                    os.remove(audio_path)
                except Exception:
                    pass

        # 2. Visual Analysis
        visual_metrics = None
        if not self.mock_transcription: # Use the same mock flag to skip heavy CV in tests
            try:
                visual_metrics = extract_visual_features(video_path)
            except Exception:
                pass

        return MediaAnalysisResult(
            transcript=transcript,
            duration=duration,
            speech_metrics=speech_metrics,
            visual_metrics=visual_metrics,
            content_analysis=content_analysis,
            media_reference=video_path
        )
