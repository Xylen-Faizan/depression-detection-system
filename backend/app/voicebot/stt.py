import whisper
import logging
import os
import wave
import numpy as np
import librosa
import base64
from pathlib import Path

logger = logging.getLogger(__name__)

class STT:
    def __init__(self):
        self.model = whisper.load_model("base")
        logger.info("Initializing Speech-to-Text engine...")

    def validate_audio_file(self, audio_path):
        if not os.path.exists(audio_path):
            return False, "Audio file does not exist"

        file_size = os.path.getsize(audio_path)
        if file_size == 0:
            return False, "Audio file is empty"

        try:
            with wave.open(audio_path, 'rb') as wav_file:
                params = wav_file.getparams()
                duration = wav_file.getnframes() / wav_file.getframerate()
                if duration < 0.5:
                    return False, f"Audio too short: {duration:.2f}s"
        except Exception as e:
            return False, f"Invalid WAV file: {e}"

        return True, ""

    def transcribe(self, audio_path):
        logger.info(f"Starting transcription for file: {audio_path}")
        is_valid, msg = self.validate_audio_file(audio_path)
        if not is_valid:
            logger.warning(f"Validation failed: {msg}")
            return "", msg

        try:
            import wave
            import numpy as np
            with wave.open(audio_path, 'rb') as wav_file:
                n_channels = wav_file.getnchannels()
                sampwidth = wav_file.getsampwidth()
                framerate = wav_file.getframerate()
                n_frames = wav_file.getnframes()
                audio_data = wav_file.readframes(n_frames)
                
                if sampwidth == 2:
                    audio_np = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0
                elif sampwidth == 4:
                    audio_np = np.frombuffer(audio_data, dtype=np.int32).astype(np.float32) / 2147483648.0
                elif sampwidth == 1:
                    audio_np = (np.frombuffer(audio_data, dtype=np.uint8).astype(np.float32) - 128.0) / 128.0
                else:
                    audio_np = whisper.load_audio(audio_path)
                    
                if n_channels == 2:
                    audio_np = audio_np.reshape(-1, 2).mean(axis=1)
                
                # Check for silence or near silence
                if np.max(np.abs(audio_np)) < 0.001:
                    return "", "Audio is completely silent"
                
                audio = audio_np
        except Exception as e:
            logger.warning(f"Native wave parsing failed: {e}")
            audio = audio_path

        result = self.model.transcribe(
            audio,
            language="en",
            task="transcribe",
            fp16=False,
            verbose=False
        )
        transcription = result["text"].strip()
        if not transcription:
            logger.warning("Whisper returned empty transcription")
            return "", "No speech detected"

        logger.info(f"Transcription successful: '{transcription}'")
        return transcription, None
