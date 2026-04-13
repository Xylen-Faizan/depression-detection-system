from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.logger import logger
from pydantic import BaseModel
import tempfile
import os
import base64
import json
from app.voicebot.depression_nlp import VoiceBot

router = APIRouter()
voice_bot = VoiceBot()


class AnalyzeRequest(BaseModel):
    text: str


@router.post("/analyze")
async def analyze_text(request: AnalyzeRequest):
    """Analyze text for depression indicators — returns confidence, severity, keywords."""
    try:
        result = voice_bot.llm.analyze_depression(request.text)
        return {
            "status": "success",
            "analysis_type": result.get("analysis_type", "unknown"),
            "is_depressed": result.get("is_depressed", False),
            "confidence": result.get("confidence", 0.5),
            "severity": result.get("severity", "mild"),
            "needs_professional_help": result.get("needs_professional_help", False),
            "keywords_found": result.get("keywords_found", []),
            "reason": result.get("reason", ""),
        }
    except Exception as e:
        logger.error(f"Text analysis failed: {e}", exc_info=True)
        return {
            "status": "error",
            "confidence": 0.5,
            "severity": "mild",
            "is_depressed": False,
            "needs_professional_help": False,
            "keywords_found": [],
            "reason": str(e),
        }

@router.websocket("/ws/conversation/{session_id}")
async def websocket_conversation(websocket: WebSocket, session_id: str):
    await websocket.accept()
    logger.info(f"WebSocket connected for session: {session_id}")

    while True:
        try:
            data = await websocket.receive_json()
            logger.info(f"Received WebSocket message: {data.get('type')}")

            if data.get("type") == "audio":
                transcription = data.get("transcription", "")
                latitude = data.get("latitude")
                longitude = data.get("longitude")
                logger.info(f"User said: '{transcription}'")

                with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmpfile:
                    wav_path = tmpfile.name

                decoded_audio = base64.b64decode(data.get("audio", ""))
                if not decoded_audio:
                    logger.warning("No audio data received")
                    continue

                with open(wav_path, "wb") as f:
                    f.write(decoded_audio)

                response = voice_bot.process_audio_for_depression(wav_path, latitude=latitude, longitude=longitude)
                os.unlink(wav_path)

                if response["audio_response"]:
                    await websocket.send_json({
                        "type": "ai_response",
                        "analysis_type": response["analysis_type"],
                        "text_response": response["response"],
                        "audio_response": base64.b64encode(response["audio_response"]).decode(),
                        "is_depressed": response["is_depressed"],
                        "confidence_score": response["confidence"],
                        "needs_professional_help": response["needs_professional_help"],
                        "transcription": transcription,
                        "helplines": response.get("helplines", [])
                    })
                else:
                    await websocket.send_json({
                        "type": "transcription_failed",
                        "message": "Could not understand the audio. Please speak clearly and try again."
                    })

        except WebSocketDisconnect:
            logger.info(f"WebSocket disconnected for session: {session_id}")
            break
        except Exception as e:
            logger.error(f"WebSocket error: {e}", exc_info=True)
            await websocket.send_json({
                "type": "error",
                "message": "Internal server error"
            })
