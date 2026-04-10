import os
from fastapi import APIRouter
from livekit.api import AccessToken, VideoGrants, LiveKitAPI
import livekit.protocol.agent_dispatch as agent_dispatch
import uuid
import logging

router = APIRouter()

@router.get("/token")
async def get_livekit_token(participant_name: str = "User", room_name: str = "clinical-session"):
    api_key = os.getenv("LIVEKIT_API_KEY")
    api_secret = os.getenv("LIVEKIT_API_SECRET")
    url = os.getenv("LIVEKIT_URL")
    
    if not api_key or not api_secret or not url:
        return {"error": "Missing LiveKit credentials! Please paste your LIVEKIT_URL, LIVEKIT_API_KEY, and LIVEKIT_API_SECRET into your .env file."}

    identity = f"{participant_name}-{uuid.uuid4().hex[:8]}"

    # Token for the user
    grant = VideoGrants(
        room_join=True,
        room=room_name,
    )
    
    access_token = AccessToken(api_key, api_secret)\
        .with_identity(identity)\
        .with_name(participant_name)\
        .with_grants(grant)
        
    jwt_token = access_token.to_jwt()

    # Explicitly dispatch the agent to this room
    try:
        async with LiveKitAPI(url, api_key, api_secret) as api:
            req = agent_dispatch.CreateAgentDispatchRequest(
                room=room_name,
                agent_name="",
            )
            dispatch = await api.agent_dispatch.create_dispatch(req)
            logging.info(f"Successfully dispatched agent to room {room_name}: {dispatch}")
    except Exception as e:
        logging.error(f"Failed to explicitly dispatch agent: {e}")

    return {"token": jwt_token, "room": room_name, "url": url}
