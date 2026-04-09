from gtts import gTTS
import io
from app.config import logger

class TTS:
    def text_to_speech(self, text, lang='en'):
        try:
            if not text.strip():
                logger.warning("Empty text provided to TTS")
                return b""

            logger.info(f"Converting text to speech: '{text[:20]}...'")
            tts = gTTS(text=text, lang=lang)
            audio_buffer = io.BytesIO()
            tts.write_to_fp(audio_buffer)
            audio_buffer.seek(0)
            audio_data = audio_buffer.getvalue()

            if len(audio_data) == 0:
                logger.error("Generated audio is empty")
                return b""

            logger.info("Audio generated successfully")
            return audio_data

        except Exception as e:
            logger.exception(f"TTS Error: {e}")
            return b""
