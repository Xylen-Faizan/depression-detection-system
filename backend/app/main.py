import sys
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import datetime

# Load .env from the project root (one level above backend/)
env_path = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(dotenv_path=env_path)

# Add the backend directory to Python path
sys.path.append(str(Path(__file__).parent.parent))

# Now import your routes
from app.routes import voice_routes, video_routes, livekit_routes, report_routes

app = FastAPI(
    title="Depression Detection API",
    description="Voice and video analysis for depression detection",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(
    voice_routes.router,
    prefix="/api/voice",
    tags=["Voice Analysis"]
)

app.include_router(
    video_routes.router,
    prefix="/api/video",
    tags=["Video Analysis"]
)

app.include_router(
    livekit_routes.router,
    prefix="/api/livekit",
    tags=["LiveKit Configuration"]
)

app.include_router(
    report_routes.router,
    prefix="/api/report",
    tags=["Report Generation"]
)

@app.get("/", include_in_schema=False)
async def root():
    return {
        "message": "Depression Detection System API",
        "endpoints": {
            "documentation": ["/docs", "/redoc"],
            "voice": "/api/voice",
            "video": "/api/video"
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
