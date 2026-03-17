import json
import logging
import os
from urllib import error, request

from dotenv import load_dotenv
from livekit import agents, api
from livekit.agents import Agent, AgentSession, RoomInputOptions
from livekit.plugins import cartesia, deepgram, noise_cancellation, openai

load_dotenv(".env")
load_dotenv(".env.local", override=True)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("outbound-agent")

OUTBOUND_TRUNK_ID = os.getenv("OUTBOUND_TRUNK_ID")
STATUS_ENDPOINT = os.getenv("STATUS_UPDATE_URL", "http://127.0.0.1:5000/internal/call_status")
STATUS_TOKEN = os.getenv("STATUS_UPDATE_TOKEN", "secret123")
OPENAI_TTS_VOICE = os.getenv("OPENAI_TTS_VOICE", "shimmer")
TTS_PROVIDER = os.getenv("TTS_PROVIDER", "openai").strip().lower()
CARTESIA_API_KEY = os.getenv("CARTESIA_API_KEY", "")
CARTESIA_VOICE_ID = os.getenv("CARTESIA_VOICE_ID", "f786b574-daa5-4673-aa0c-cbe3e8534c02")

OPENING_GREETING = (
    "Hello sir, good afternoon. Main Riya bol rahi hu SGI Aiiot Robotics se. "
    "Aapne shayad hamare smart energy meter ya industrial automation solutions mein interest dikhaya tha. "
    "Kya abhi baat karne ke liye ek minute sahi rahega?"
)

FIRST_REPLY_INSTRUCTION = (
    "Start speaking immediately after the call is answered. "
    "Do not wait for the customer to speak first. "
    "Use this exact opening in a warm, human, natural female voice: "
    f"'{OPENING_GREETING}'"
)

AGENT_INSTRUCTIONS = """
You are Riya, a warm and confident female caller from SGI Aiiot Robotics.

Your job is to sound natural, polite, and human. The customer should feel like they are speaking to a real Indian female executive, not a robotic voice bot.

Speaking rules:
- Speak in smooth natural Hinglish.
- Always use feminine phrasing like "bol rahi hu", "kar rahi hu", "bata rahi hu".
- Never use masculine phrasing like "kar raha hu".
- Keep sentences short and conversational.
- Avoid sounding like a script reader.
- Avoid long monologues.
- Respond quickly and naturally.
- Use a warm, calm, friendly sales tone.
- Add light human fillers only when natural, like "ji", "bilkul", "achha", "samajh gayi".

Opening behavior:
- The moment the call is answered, start speaking first.
- Do not wait for the user to say hello.
- Keep the first greeting warm and short.

What SGI offers:
- Smart WiFi energy meters
- Vision based machine security systems
- Industrial IoT sensors
- Machine monitoring dashboards

WiFi Energy Meter:
- Explain that it tracks electricity usage in real time.
- Explain that users can see usage on mobile or dashboard.
- Approximate price is around Rs 24,999.
- Mention that final price can vary depending on installation and requirement.

Other pricing:
- Do not give exact pricing for other products.
- Say pricing depends on requirement and the team can share a proper quotation.

If the customer asks for human support, manager, callback, demo, or quotation:
- Confirm politely.
- Say that the SGI team will call them back shortly.

If you need a moment:
- Say only: "Ek second ji..."

Ending style:
- End warmly and briefly.
- Example style: "Thank you sir, aapse baat karke achha laga. Hamari team aapse jaldi connect karegi."
"""


def normalize_phone(value):
    raw = str(value or "").strip()
    if not raw:
        return ""
    if raw.startswith("sip:"):
        return raw
    digits = "".join(ch for ch in raw if ch.isdigit() or ch == "+")
    if digits and not digits.startswith("+"):
        digits = f"+{digits}"
    return digits


def get_tts_provider():
    if TTS_PROVIDER == "cartesia" and CARTESIA_API_KEY:
        return cartesia.TTS(
            api_key=CARTESIA_API_KEY,
            model="sonic-3",
            language="hi",
            voice=CARTESIA_VOICE_ID,
            speed=0.95,
        )

    return openai.TTS(
        model="gpt-4o-mini-tts",
        voice=OPENAI_TTS_VOICE,
    )


def push_status(call_id, status, message):
    if not call_id:
        return

    payload = json.dumps({"call_id": call_id, "status": status, "message": message}).encode("utf-8")
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
        logger.warning("Unable to push status update: %s", exc)


def classify_call_error(error_text):
    text = error_text.lower()

    if "no answer" in text or "no response" in text or "timeout" in text:
        return "rejected", "Customer did not answer the scheduled call."

    if "busy" in text or "declined" in text or "rejected" in text:
        return "rejected", "Customer rejected or was busy on the call."

    if "invalid" in text or "not found" in text or "malformed" in text:
        return "invalid", "Phone number looks invalid for outbound dialing."

    return "rejected", f"Scheduled call could not be completed: {error_text}"


class OutboundAssistant(Agent):
    def __init__(self):
        super().__init__(instructions=AGENT_INSTRUCTIONS)


async def entrypoint(ctx: agents.JobContext):
    logger.info("Connecting to room %s", ctx.room.name)

    phone_number = None
    call_id = None

    try:
        if ctx.job.metadata:
            data = json.loads(ctx.job.metadata)
            phone_number = data.get("phone_number")
            call_id = data.get("call_id")
    except Exception:
        logger.warning("No metadata")

    session = AgentSession(
        stt=deepgram.STT(
            model="nova-3",
            language="hi",
        ),
        llm=openai.LLM(
            model="gpt-4o-mini",
            temperature=0.2,
        ),
        tts=get_tts_provider(),
    )

    await session.start(
        room=ctx.room,
        agent=OutboundAssistant(),
        room_input_options=RoomInputOptions(
            noise_cancellation=noise_cancellation.BVCTelephony(),
            close_on_disconnect=True,
        ),
    )

    if phone_number:
        logger.info("Calling %s", phone_number)
        push_status(call_id, "ringing", "Phone is ringing. Waiting for customer to pick up.")

        try:
            await ctx.api.sip.create_sip_participant(
                api.CreateSIPParticipantRequest(
                    room_name=ctx.room.name,
                    sip_trunk_id=OUTBOUND_TRUNK_ID,
                    sip_call_to=phone_number,
                    participant_identity=f"sip_{phone_number}",
                    wait_until_answered=True,
                )
            )

            logger.info("Call answered")
            push_status(call_id, "answered", "Call initiated successfully. Customer picked up.")

            await session.generate_reply(instructions=FIRST_REPLY_INSTRUCTION)

        except Exception as exc:
            logger.error("Call failed %s", exc)
            status, message = classify_call_error(str(exc))
            push_status(call_id, status, message)
            ctx.shutdown()

    else:
        logger.info("Inbound call")
        await session.generate_reply(
            instructions="Greet the caller immediately in a warm, natural, human female voice."
        )


if __name__ == "__main__":
    agents.cli.run_app(
        agents.WorkerOptions(
            entrypoint_fnc=entrypoint,
            agent_name="outbound-caller",
        )
    )
