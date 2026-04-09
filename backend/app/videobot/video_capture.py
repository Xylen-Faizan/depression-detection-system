import cv2
import time
import logging
import threading
import numpy as np
from datetime import datetime
from typing import Optional, Dict, Any
from collections import defaultdict, Counter
from .emotion_detector import EmotionDetector

logger = logging.getLogger("DepressionDetection")

class VideoCapture:
    """Video analysis manager with WebSocket support for real-time emotion detection"""

    # Emotion to depression score mapping
    EMOTION_TO_DEPRESSION_SCORE = {
        "happy": 0.1,
        "neutral": 0.5,
        "sad": 0.8,
        "angry": 0.9,
        "fear": 0.85,
        "disgust": 0.8,
        "surprise": 0.4
    }

    # Singleton pattern
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, '_initialized'):
            return

        self._initialized = True
        self.emotion_detector = EmotionDetector()
        self.active_sessions = {}
        self.lock = threading.Lock()
        logger.info("VideoCapture initialized with WebSocket support")

    async def process_frame(self, frame_data: bytes, session_id: str) -> Dict[str, Any]:
        """Process individual frames from WebSocket"""
        try:
            # Decode frame
            nparr = np.frombuffer(frame_data, np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

            if frame is None:
                logger.error("Failed to decode WebSocket frame")
                return {"error": "Invalid frame data"}

            # Detect emotion
            emotion = self.emotion_detector.detect_emotion(frame)
            score = self.EMOTION_TO_DEPRESSION_SCORE.get(emotion, 0.5)

            # Update session data
            with self.lock:
                if session_id not in self.active_sessions:
                    self.active_sessions[session_id] = {
                        "start_time": datetime.utcnow(),
                        "emotions": [],
                        "last_frame_time": None
                    }

                self.active_sessions[session_id]["emotions"].append(emotion)
                self.active_sessions[session_id]["last_frame_time"] = datetime.utcnow()

            return {
                "emotion": emotion,
                "score": score,
                "timestamp": datetime.utcnow().isoformat()
            }

        except Exception as e:
            logger.exception("Frame processing failed")
            return {"error": str(e)}

    def get_session_results(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get results for a session"""
        with self.lock:
            session = self.active_sessions.get(session_id)
            if not session:
                return None

            return self._generate_result(session_id, session["emotions"])

    def cleanup_session(self, session_id: str) -> None:
        """Clean up session resources"""
        with self.lock:
            if session_id in self.active_sessions:
                del self.active_sessions[session_id]

    def _generate_result(self, session_id: str, emotions: list) -> Dict[str, Any]:
        """Generate analysis results from emotion list"""
        total_samples = len(emotions)
        result = {
            "dominant_emotion": "neutral",
            "score": 0.5,
            "total_samples": total_samples,
            "session_id": session_id,
            "timestamp": datetime.utcnow().isoformat()
        }

        if emotions:
            counter = Counter(emotions)
            result["dominant_emotion"] = counter.most_common(1)[0][0]
            result["score"] = round(
                self.EMOTION_TO_DEPRESSION_SCORE.get(
                    result["dominant_emotion"], 0.5
                ), 2
            )

        return result
