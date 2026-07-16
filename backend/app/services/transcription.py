import subprocess
import os
from faster_whisper import WhisperModel
from typing import Tuple, Optional
from ..config.settings import settings
import uuid


class TranscriptionService:
    _instance = None
    _model = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def _load_model(self) -> WhisperModel:
        if self._model is None:
            self._model = WhisperModel(
                model_size_or_path=settings.WHISPER_MODEL_SIZE,
                device=settings.WHISPER_DEVICE
            )
        return self._model

    def extract_audio_from_video(self, video_path: str, output_path: str) -> bool:
        """
        Uses FFmpeg to extract the audio track from a video file.
        This prepares the file for Whisper to transcribe.
        """
        try:
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            ffmpeg_command = [
                "ffmpeg",
                "-i", video_path,
                "-vn",
                "-acodec", "pcm_s16le",
                "-ar", "16000",
                "-ac", "1",
                output_path,
                "-y"
            ]
            subprocess.run(ffmpeg_command, check=True, capture_output=True)
            return True
        except subprocess.CalledProcessError:
            return False

    def transcribe_audio(self, audio_path: str) -> Tuple[str, list]:
        """
        Passes an audio file to the Whisper model to generate a full transcript 
        and a list of timestamped segments.
        """
        model = self._load_model()
        segments, info = model.transcribe(audio_path)
        
        transcript_text = ""
        segments_list = []
        
        for segment in segments:
            transcript_text += segment.text + " "
            segments_list.append({
                "start": str(segment.start),
                "end": str(segment.end),
                "text": segment.text,
                "language": info.language
            })
        
        return transcript_text.strip(), segments_list

    def transcribe_video(self, video_path: str, output_dir: str) -> Tuple[str, Optional[str], list]:
        os.makedirs(output_dir, exist_ok=True)
        
        audio_filename = f"{uuid.uuid4().hex}.wav"
        audio_path = os.path.join(output_dir, audio_filename)
        
        if not self.extract_audio_from_video(video_path, audio_path):
            return "", None, []
        
        transcript, segments = self.transcribe_audio(audio_path)
        
        transcript_filename = f"{uuid.uuid4().hex}.txt"
        transcript_path = os.path.join(output_dir, transcript_filename)
        
        with open(transcript_path, "w", encoding="utf-8") as transcript_file:
            transcript_file.write(transcript)
        
        return transcript, transcript_path, segments

    def transcribe_audio_file(self, audio_path: str, output_dir: str) -> Tuple[str, Optional[str], list]:
        transcript, segments = self.transcribe_audio(audio_path)
        
        os.makedirs(output_dir, exist_ok=True)
        transcript_filename = f"{uuid.uuid4().hex}.txt"
        transcript_path = os.path.join(output_dir, transcript_filename)
        
        with open(transcript_path, "w", encoding="utf-8") as transcript_file:
            transcript_file.write(transcript)
        
        return transcript, transcript_path, segments


transcription_service = TranscriptionService()