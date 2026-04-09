import os
from pathlib import Path
from dotenv import load_dotenv
import logging
import sys

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("depression_detection.log", mode='a')
    ]
)
logger = logging.getLogger("DepressionDetection")

# Load .env file from project root
project_root = Path(__file__).parent.parent.parent  # Points to depression_detection_system/
dotenv_path = project_root / ".env"

if dotenv_path.exists():
    load_dotenv(dotenv_path)
    logger.info(f"Loaded .env from {dotenv_path}")
else:
    logger.warning(f".env file not found at {dotenv_path}")

# Now read environment variables
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL_NAME = os.getenv("GROQ_MODEL_NAME", "meta-llama/llama-4-scout-17b-16e-instruct")
OPENCAGE_API_KEY = os.getenv("OPENCAGE_API_KEY")

# Validate required keys
if not GROQ_API_KEY:
    logger.error("GROQ_API_KEY not set in environment variables")
    logger.error("Please set GROQ_API_KEY in your .env file or environment variables")
else:
    logger.info("GROQ_API_KEY found")


# Paths
MODELS_DIR = project_root / "backend" / "models"
FACE_MODEL_PATH = MODELS_DIR / "face_model.h5"

# Validate model file
if FACE_MODEL_PATH.exists():
    logger.info(f"Face model found at {FACE_MODEL_PATH}")
else:
    logger.warning(f"Face model not found at {FACE_MODEL_PATH}")

# Supported Languages
SUPPORTED_LANGUAGES = {
    'en': 'English',
    'es': 'Spanish',
    'fr': 'French',
    'de': 'German',
    'hi': 'Hindi'
}

# Emotions from face_model.h5
EMOTIONS = ['angry', 'disgust', 'fear', 'happy', 'neutral', 'sad', 'surprise']

# Audio processing settings
AUDIO_SETTINGS = {
    "sample_rate": 16000,
    "channels": 1,
    "chunk_size": 1024,
    "format": "wav",
    "max_duration": 300,  # 5 minutes max
    "min_duration": 0.5   # 0.5 seconds min
}

# Video processing settings
VIDEO_SETTINGS = {
    "max_duration": 1800,  # 30 minutes
    "analysis_interval": 2,  # seconds
    "frame_width": 640,
    "frame_height": 480
}

# Depression analysis settings
DEPRESSION_ANALYSIS = {
    "voice_weight": 0.7,
    "video_weight": 0.3,
    "confidence_threshold": 0.6,
    "depression_keywords": [
        "sad", "depressed", "hopeless", "worthless", "tired",
        "empty", "lonely", "anxious", "worried", "stressed"
    ]
}

# Check dependencies
def check_dependencies():
    """Check if required dependencies are available"""
    missing_deps = []

    try:
        import whisper
        logger.info("Whisper available")
    except ImportError:
        missing_deps.append("openai-whisper")
        logger.error("Whisper not available")

    try:
        import cv2
        logger.info("OpenCV available")
    except ImportError:
        missing_deps.append("opencv-python")
        logger.error("OpenCV not available")

    try:
        import tensorflow
        logger.info("TensorFlow available")
    except ImportError:
        missing_deps.append("tensorflow")
        logger.error("TensorFlow not available")

    try:
        import pydub
        logger.info("Pydub available")
    except ImportError:
        missing_deps.append("pydub")
        logger.error("Pydub not available")

    try:
        import gtts
        logger.info("gTTS available")
    except ImportError:
        missing_deps.append("gtts")
        logger.error("gTTS not available")

    try:
        import groq
        if GROQ_API_KEY:
            logger.info("Groq client available with API key")
        else:
            logger.warning("Groq client available but no API key")
    except ImportError:
        missing_deps.append("groq")
        logger.error("Groq client not available")

    if missing_deps:
        logger.error(f"Missing dependencies: {', '.join(missing_deps)}")
        logger.error("Install missing dependencies with: pip install " + " ".join(missing_deps))
        return False, missing_deps
    else:
        logger.info("All dependencies available")
        return True, []

# Check system requirements
def check_system_requirements():
    """Check system requirements and configurations"""
    issues = []

    # Check disk space for temporary files
    import shutil
    free_space = shutil.disk_usage(".")[2] / (1024**3)  # GB
    if free_space < 1:
        issues.append(f"Low disk space: {free_space:.2f}GB available")

    # Check if ffmpeg is available (for pydub)
    try:
        from pydub.utils import which
        if not which("ffmpeg"):
            issues.append("FFmpeg not found - audio conversion may fail")
    except:
        pass

    if issues:
        for issue in issues:
            logger.warning(f"{issue}")

    return len(issues) == 0, issues

# Initialize checks
deps_ok, missing_deps = check_dependencies()
system_ok, system_issues = check_system_requirements()

if not deps_ok:
    logger.error("System not ready - missing dependencies")
if not system_ok:
    logger.warning("System has configuration issues")

logger.info("Configuration loaded successfully")
