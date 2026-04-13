from dotenv import load_dotenv
import os
import logging
import asyncio
import requests
from pathlib import Path

# Load .env from the project root (one level above backend/)
env_path = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(dotenv_path=env_path)

from livekit import agents
from livekit.agents import AgentSession, Agent, RoomInputOptions, function_tool, RunContext
from livekit.plugins import google
from google.genai import types
from app.voicebot.helpline_service import HelplineService

AGENT_INSTRUCTION = """
You are Serene, an empathetic, patient AI mental healthcare clinical assistant.
Your goal is to gently listen, validate feelings, and provide a safe, unhurried therapeutic space.
Act exactly like a highly skilled, experienced human therapist in a quiet clinic.

[LANGUAGE — CRITICAL]
You MUST always speak and respond ONLY in English, regardless of what language or accent the user speaks in.
Transcribe and interpret all user speech as English.

[CONVERSATIONAL STYLE — CRITICAL]
- Be PATIENT. Never rush. Let the user fully finish speaking before you respond.
- Do NOT interrupt mid-sentence. If the user pauses briefly, WAIT — they may be collecting their thoughts.
- Give thoughtful, measured responses — not rapid-fire replies.
- Keep responses empathetic, warm, and between 2-4 sentences. Use open-ended follow-ups.
- Speak in a calm, gentle, clinical tone — like a real therapist sitting across from the patient.
- Avoid sounding robotic or scripted. Use natural, conversational language.
- Acknowledge what the user said specifically — reflect their words back to show you truly listened.

[CRITICAL BEHAVIOR — MENTAL HEALTH PROTOCOL]
You must rigorously differentiate between general depression and imminent danger (Confidence > 0.8).

1. IF THE USER IS SAD/HOPELESS (e.g., "I am hopeless", "I don't know what to do", "I'm feeling down"):
   - DO NOT call the emergency helpline tool!
   - You MUST act as a soothing therapist. Try to calm them down, make them feel relaxed, validate their struggle, and help them process their emotions gently.

2. IF THE USER IS IN IMMINENT DANGER (e.g., expressing suicidal thoughts, severe trauma, feeling completely out of control, self-harm):
   - You MUST issue a red alert by calling the `get_emergency_helplines` tool RIGHT AWAY.
   - Do NOT ask for permission. Call the tool silently and immediately provide the helpline numbers to protect their life.
"""

SESSION_INSTRUCTION = "Begin the conversation by saying: 'Hello. I'm Serene, your personal clinical assistant. I'm here to listen — take your time. How are you feeling today?'"

helpline_svc = HelplineService()


def _auto_detect_location():
    """Auto-detect the user's approximate location via IP geolocation."""
    try:
        resp = requests.get("https://ipapi.co/json/", timeout=4)
        if resp.status_code == 200:
            data = resp.json()
            lat = data.get("latitude")
            lng = data.get("longitude")
            if lat and lng:
                logging.info(f"Auto-detected location: lat={lat}, lng={lng} ({data.get('city')}, {data.get('region')}, {data.get('country_name')})")
                return float(lat), float(lng)
    except Exception as e:
        logging.warning(f"IP geolocation failed: {e}")
    # Default fallback: New Delhi, India
    logging.info("Using default location: New Delhi, India")
    return 28.6139, 77.2090


@function_tool()
async def get_emergency_helplines(context: RunContext) -> str:
    """Get real-time nearby mental health emergency helplines. Call this immediately when a user expresses distress, depression, hopelessness, or suicidal thoughts. No parameters needed — location is auto-detected."""
    logging.info("get_emergency_helplines tool called — auto-detecting location...")
    try:
        # Run blocking HTTP calls in a thread pool to avoid freezing the event loop
        lat, lng = await asyncio.to_thread(_auto_detect_location)
        helplines = await asyncio.to_thread(helpline_svc.get_nearest_helplines, lat, lng)
    except Exception as e:
        logging.error(f"Helpline lookup failed: {e}")
        helplines = []

    if not helplines:
        return "Here are some general mental health helplines: 1. iCall — 9152987821, 2. Vandrevala Foundation — 1860-2662-345, 3. NIMHANS — 080-46110007. Please reach out to any of them right away."
    result_lines = []
    for i, h in enumerate(helplines[:3], 1):
        result_lines.append(f"{i}. {h['name']} — {h['number']}")
    return "Here are the 3 nearest mental health helplines for the user. Read them out clearly:\n" + "\n".join(result_lines)


class Assistant(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions=AGENT_INSTRUCTION,
            llm=google.beta.realtime.RealtimeModel(
                voice="Aoede",
                temperature=0.7,
                language="en-US",
                # Turn detection: LOW end-of-speech sensitivity = waits longer before
                # deciding the user is done speaking. Silence padding = 2000ms.
                realtime_input_config=types.RealtimeInputConfig(
                    automatic_activity_detection=types.AutomaticActivityDetection(
                        end_of_speech_sensitivity=types.EndSensitivity.END_SENSITIVITY_LOW,
                        silence_duration_ms=2500,
                        prefix_padding_ms=0,
                    )
                ),
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

