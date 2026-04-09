from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.logger import logger
import numpy as np
from datetime import datetime
from typing import Optional
from app.videobot.video_capture import VideoCapture

router = APIRouter()
video_capture = VideoCapture()

@router.websocket("/ws/video/{session_id}")
async def video_websocket(websocket: WebSocket, session_id: str):
    await websocket.accept()
    logger.info(f"Video WebSocket connected for session: {session_id}")

    try:
        while True:
            # Receive frame as bytes
            data = await websocket.receive_bytes()

            # Process frame
            result = await video_capture.process_frame(data, session_id)

            if "error" in result:
                await websocket.send_json({"type": "error", "message": result["error"]})
                continue

            await websocket.send_json({
                "type": "analysis",
                "emotion": result["emotion"],
                "score": result["score"],
                "timestamp": result["timestamp"]
            })

    except WebSocketDisconnect:
        logger.info(f"Video WebSocket disconnected for session: {session_id}")
        video_capture.cleanup_session(session_id)
    except Exception as e:
        logger.error(f"Video WebSocket error: {str(e)}")
        await websocket.send_json({"type": "error", "message": str(e)})
        video_capture.cleanup_session(session_id)

@router.get("/results/{session_id}")
async def get_video_results(session_id: str):
    """Get stored video analysis results"""
    try:
        results = video_capture.get_session_results(session_id)
        if not results:
            return {
                "status": "error",
                "message": "No results found for this session"
            }

        return {
            "status": "success",
            "results": results
        }
    except Exception as e:
        logger.error(f"Error retrieving video results: {str(e)}")
        return {
            "status": "error",
            "message": str(e)
        }
