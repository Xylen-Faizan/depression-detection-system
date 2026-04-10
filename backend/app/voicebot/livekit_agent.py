from dotenv import load_dotenv
import os
import logging
from pathlib import Path

# Load .env from the project root (one level above backend/)
env_path = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(dotenv_path=env_path)

from livekit import agents
from livekit.agents import AgentSession, Agent, RoomInputOptions, function_tool, RunContext
from livekit.plugins import google
from app.voicebot.helpline_service import HelplineService

AGENT_INSTRUCTION = """
You are Serene, an empathetic, active-listening AI mental healthcare assistant.
Your goal is to gently listen to the user, validate their feelings, and provide a safe space for them to talk.
When they speak, acknowledge their emotions compassionately.
Always speak in a very calm, supportive, and natural conversational tone.
Keep your responses relatively brief, empathetic, and open-ended to encourage them to share more.

[IMPORTANT]
If the user expresses feelings of hopelessness, severe despair, self-harm, or explicitly states they are depressed, you MUST:
1. Reassure them that they are not alone.
2. Strongly encourage them to reach out to professional help or a helpline.
"""

SESSION_INSTRUCTION = "Begin the conversation by saying: 'Hello. I'm Serene, your personal clinical assistant. I'm here to listen. How are you feeling today?'"

helpline_svc = HelplineService()

@function_tool()
async def get_emergency_helplines(context: RunContext, latitude: float, longitude: float) -> str:
    """Get real-time nearby mental health emergency helplines to provide to the user if they are in despair."""
    logging.info(f"Fetching helplines for lat={latitude}, lng={longitude}")
    lat = latitude if latitude is not None else 28.6139
    lng = longitude if longitude is not None else 77.2090
    helplines = helpline_svc.get_helplines_by_location(lat, lng)
    return f"Please provide these helplines to the user: {helplines}"

class Assistant(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions=AGENT_INSTRUCTION,
            llm=google.beta.realtime.RealtimeModel(
                voice="Aoede",
                temperature=0.7,
            ),
            tools=[get_emergency_helplines],
        )

async def entrypoint(ctx: agents.JobContext):
    session = AgentSession()
    try:
        await session.start(
            room=ctx.room,
            agent=Assistant(),
            room_input_options=RoomInputOptions(
                video_enabled=False
            )
        )
        await ctx.connect()
        await session.generate_reply(
            instructions=SESSION_INSTRUCTION,
        )
    except Exception as e:
        logging.error(f"Failed to connect to LiveKit: {e}")
        raise

if __name__ == "__main__":
    agents.cli.run_app(agents.WorkerOptions(entrypoint_fnc=entrypoint))
