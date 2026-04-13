from fastapi import APIRouter
from fastapi.responses import Response
from fastapi.logger import logger
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from app.utils.report_generator import ReportGenerator

router = APIRouter()
report_gen = ReportGenerator()


class VoiceMessage(BaseModel):
    text: str
    isAgent: bool = False
    confidence: Optional[float] = None
    severity: Optional[str] = None
    is_depressed: Optional[bool] = None
    needs_professional_help: Optional[bool] = None
    timestamp: Optional[float] = None


class FacialEmotion(BaseModel):
    emotion: str
    score: float
    timestamp: Optional[str] = None


class ReportRequest(BaseModel):
    session_id: str = "SESSION"
    session_duration_seconds: float = 0
    voice_messages: List[VoiceMessage] = []
    facial_emotions: List[FacialEmotion] = []
    voice_average_confidence: float = 0
    facial_average_score: float = 0
    combined_score: float = 0


@router.post("/generate")
async def generate_report(request: ReportRequest):
    """Generate a medical-grade PDF depression screening report."""
    try:
        session_data = {
            "session_id": request.session_id,
            "session_duration_seconds": request.session_duration_seconds,
            "voice_messages": [m.dict() for m in request.voice_messages],
            "facial_emotions": [e.dict() for e in request.facial_emotions],
            "voice_average_confidence": request.voice_average_confidence,
            "facial_average_score": request.facial_average_score,
            "combined_score": request.combined_score,
        }

        pdf_bytes = report_gen.generate(session_data)

        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename=serene_care_report_{request.session_id}.pdf"
            }
        )
    except Exception as e:
        logger.error(f"Report generation failed: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}
