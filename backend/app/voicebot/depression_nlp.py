from .stt import STT
from .tts import TTS
from .llm import LLMProcessor
from .helpline_service import HelplineService
import logging

logger = logging.getLogger(__name__)

class VoiceBot:
    def __init__(self):
        self.stt = STT()
        self.tts = TTS()
        self.llm = LLMProcessor()
        self.confidence = 0.5
        logger.info("VoiceBot initialized successfully")

    def process_audio_for_depression(self, audio_path, latitude=None, longitude=None):
        try:
            transcription, error = self.stt.transcribe(audio_path)
            if not transcription:
                return {
                    "analysis_type": "error",
                    "is_depressed": False,
                    "confidence": 0.5,
                    "response": "Audio could not be understood.",
                    "audio_response": b""
                }

            result = self.llm.analyze_depression(transcription)
            
            # High Risk Trigger Condition
            is_high_risk = (
                result.get("severity") == "severe" or
                result.get("needs_professional_help") == True or
                result.get("confidence", 0) >= 0.75
            )

            helplines = []
            if is_high_risk:
                helplines = HelplineService.get_nearest_helplines(latitude, longitude)
                if helplines:
                    helpline_text = "\n\nIf you need immediate help, please reach out:\n"
                    for idx, hl in enumerate(helplines, start=1):
                        helpline_text += f"{idx}. {hl['name']} — {hl['number']}\n"
                    result["response"] += helpline_text

            audio_response = self.tts.text_to_speech(result["response"])

            return {
                "analysis_type": result.get("analysis_type", "unknown"),
                "is_depressed": result["is_depressed"],
                "confidence": result["confidence"],
                "response": result["response"],
                "audio_response": audio_response,
                "needs_professional_help": result.get("needs_professional_help", False),
                "helplines": helplines
            }
        except Exception as e:
            return {
                "analysis_type": "error",
                "is_depressed": False,
                "confidence": 0.5,
                "response": "Error analyzing your message.",
                "audio_response": b"",
                "needs_professional_help": False,
                "helplines": []
            }
