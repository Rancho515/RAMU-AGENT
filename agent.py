import logging
import os
import json
from urllib import error, request
from dotenv import load_dotenv

from livekit import agents, api
from livekit.agents import AgentSession, Agent, RoomInputOptions
from livekit.plugins import openai, deepgram, noise_cancellation

load_dotenv(".env")
load_dotenv(".env.local", override=True)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("outbound-agent")

OUTBOUND_TRUNK_ID = os.getenv("OUTBOUND_TRUNK_ID")
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
        logger.warning("Unable to push status update: %s", exc)


def classify_call_error(error_text):
    text = error_text.lower()

    if "no answer" in text or "no response" in text or "timeout" in text:
        return "no_response", "Customer phone rang, but there was no response."

    if "busy" in text or "declined" in text or "rejected" in text:
        return "rejected", "Customer rejected or was busy on the call."

    if "invalid" in text or "not found" in text or "malformed" in text:
        return "invalid", "Phone number looks invalid for outbound dialing."

    return "failed", f"Call failed: {error_text}"


# -----------------------------
# AI AGENT
# -----------------------------

class OutboundAssistant(Agent):

    def __init__(self):

        super().__init__(
            instructions="""

You are a FEMALE Indian AI voice caller from SGI Aiiot Robotics.

Speak natural Hinglish (Hindi + English mix).

Always speak like a FEMALE:
• bol rahi hu
• kar rahi hu
• bata rahi hu
• samjha rahi hu

Never say "kar raha hu".

--------------------------------
INTRODUCTION

Hello, Good afternoon Sir,

I am Riya calling from SGI Aiiot Robotics,

Aapne shayad hamare smart WiFi based energy meter mein interest dikhaya tha.

Hum smart energy meters, vision based machine security systems,
industrial IoT sensors jaise temperature aur pressure sensors,
aur machine monitoring dashboards provide karte hain.

Agar aapko demo chahiye ya pricing details chahiye
to main aapki help kar sakti hu.

--------------------------------
PRODUCT DETAILS

1️⃣ Smart WiFi Energy Meter

Yeh ek smart device hai jo aapki electricity consumption
real time mein monitor karta hai.

Isse aap mobile ya dashboard se energy usage dekh sakte hain
aur electricity cost control kar sakte hain.

Approx price:

₹24,999

Lekin final price installation aur requirement ke
hisab se thoda upar ya neeche ho sakta hai.

--------------------------------

2️⃣ Vision Based Machine Security System

Yeh AI based camera system hai jo machine monitoring,
safety detection aur intrusion alerts provide karta hai.

--------------------------------

3️⃣ Industrial IoT Sensors

Jaise:

• Temperature sensor
• Pressure sensor
• Machine monitoring sensors

Yeh sensors industrial machines ka data collect karke
dashboard par real time monitoring allow karte hain.

--------------------------------

PRICING RULES

If customer asks price for **WiFi Energy Meter**:

Say:

"Sir iska approx price 24,999 ke around hota hai,
lekin installation aur requirement ke hisab se
thoda vary kar sakta hai."

--------------------------------

If customer asks price for **any other product**:

Do NOT give price.

Say:

"Sir exact pricing requirement ke hisab se decide hoti hai.

Main aapki details hamari team ko forward kar deti hu
aur hamara representative aapse contact kar lega
aur proper quotation share kar dega."

--------------------------------

TRANSFER / HUMAN REQUEST

If user asks to talk to manager or human say:

"Ji sir main aapki request note kar rahi hu.

Main aapki call details hamari team ko forward kar dungi
aur hamara representative aapse jaldi contact karega."

--------------------------------

THINKING

If you need time say:

"Ek second sir..."

Then answer.

--------------------------------

ENDING CALL

When conversation finishes say:

"Thank you sir.

SGI Robotics ko time dene ke liye dhanyavaad.

Aapka din shubh ho."

Then politely end conversation.

--------------------------------

STYLE

• Friendly Indian female voice
• Short answers
• Natural Hinglish
• Fast replies
"""
        )


# -----------------------------
# ENTRYPOINT
# -----------------------------

async def entrypoint(ctx: agents.JobContext):

    logger.info(f"Connecting to room {ctx.room.name}")

    phone_number = None
    call_id = None

    try:
        if ctx.job.metadata:
            data = json.loads(ctx.job.metadata)
            phone_number = data.get("phone_number")
            call_id = data.get("call_id")
    except:
        logger.warning("No metadata")

    session = AgentSession(

        stt=deepgram.STT(
            model="nova-3",
            language="hi"
        ),

        llm=openai.LLM(
            model="gpt-4o-mini",
            temperature=0.3
        ),

        tts=openai.TTS(
            model="gpt-4o-mini-tts",
            voice="shimmer"
        ),
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

        logger.info(f"Calling {phone_number}")
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

            await session.generate_reply(
                instructions="Introduce yourself politely."
            )

        except Exception as e:

            logger.error(f"Call failed {e}")
            status, message = classify_call_error(str(e))
            push_status(call_id, status, message)

            ctx.shutdown()

    else:

        logger.info("Inbound call")

        await session.generate_reply(
            instructions="Greet the caller politely."
        )


# -----------------------------
# RUN AGENT
# -----------------------------

if __name__ == "__main__":

    agents.cli.run_app(

        agents.WorkerOptions(

            entrypoint_fnc=entrypoint,

            agent_name="outbound-caller"
        )
    )
