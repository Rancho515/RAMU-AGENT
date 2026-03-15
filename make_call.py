import argparse
import asyncio
import os
import random
import json
from urllib import error, request
from dotenv import load_dotenv
from livekit import api

# Load environment variables
load_dotenv(".env")
load_dotenv(".env.local", override=True)
STATUS_ENDPOINT = os.getenv("STATUS_UPDATE_URL", "http://127.0.0.1:5000/internal/call_status")
STATUS_TOKEN = os.getenv("STATUS_UPDATE_TOKEN", "secret123")


def push_status(call_id, status, message):
    if not call_id:
        return

    payload = json.dumps(
        {"call_id": call_id, "status": status, "message": message}
    ).encode("utf-8")
    req = request.Request(
        STATUS_ENDPOINT,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "X-Status-Token": STATUS_TOKEN,
        },
        method="POST",
    )

    try:
        with request.urlopen(req, timeout=5):
            return
    except error.URLError as exc:
        print(f"Warning: could not push status update: {exc}")

async def main():
    parser = argparse.ArgumentParser(description="Make an outbound call via LiveKit Agent.")
    parser.add_argument("--to", required=True, help="The phone number to call (e.g., +91...)")
    parser.add_argument("--call-id", required=True, help="The database ID for this call.")
    args = parser.parse_args()

    # 1. Validation
    phone_number = args.to.strip()
    call_id = str(args.call_id).strip()
    if not phone_number.startswith("+"):
        push_status(call_id, "invalid", "Phone number must start with country code.")
        print("Error: Phone number must start with '+' and country code.")
        return

    url = os.getenv("LIVEKIT_URL")
    api_key = os.getenv("LIVEKIT_API_KEY")
    api_secret = os.getenv("LIVEKIT_API_SECRET")

    if not (url and api_key and api_secret):
        push_status(call_id, "failed", "LiveKit credentials missing in environment.")
        print("Error: LiveKit credentials missing in .env.local")
        return

    # 2. Setup API Client
    lk_api = api.LiveKitAPI(url=url, api_key=api_key, api_secret=api_secret)

    # 3. Create a unique room for this call
    # We use a random suffix to ensure room names are unique
    room_name = f"call-{phone_number.replace('+', '')}-{random.randint(1000, 9999)}"

    print(f"Initating call to {phone_number}...")
    print(f"Session Room: {room_name}")

    try:
        # 4. Dispatch the Agent
        # We explicitly tell LiveKit to send the 'outbound-caller' agent to this room.
        # We pass the phone number in the 'metadata' field so the agent knows who to dial.
        dispatch_request = api.CreateAgentDispatchRequest(
            agent_name="outbound-caller", # Must match agent.py
            room=room_name,
            metadata=json.dumps({"phone_number": phone_number, "call_id": call_id})
        )
        
        dispatch = await lk_api.agent_dispatch.create_dispatch(dispatch_request)
        push_status(call_id, "calling", "AI agent joined. Dialing customer now.")

        print("\n Call Dispatched Successfully!")
        print(f"Dispatch ID: {dispatch.id}")
        print("-" * 40)
        print("The agent is now joining the room and will dial the number.")
        print("Check your agent terminal for logs.")
        
    except Exception as e:
        push_status(call_id, "failed", f"Error dispatching call: {e}")
        print(f"\n Error dispatching call: {e}")
    
    finally:
        await lk_api.aclose()

if __name__ == "__main__":
    asyncio.run(main())
