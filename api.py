import os
import asyncio
import sqlite3
import logging
import httpx
from fastapi import FastAPI, Request, Form
from fastapi.responses import PlainTextResponse

# ── Machine 3 — Omnichannel AI Sales Closer ──
from leados_sales import run_sales_agent
from twilio.twiml.messaging_response import MessagingResponse

# Configure structured logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="ZRAI Machine 3 - Twilio Webhook Router")

# ─────────────────────────────────────────────────────────────────────────────
# TWILIO CONFIG
# ─────────────────────────────────────────────────────────────────────────────

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN  = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_FROM        = os.getenv("TWILIO_FROM_NUMBER") or os.getenv("TWILIO_PHONE_NUMBER", "")


# ─────────────────────────────────────────────────────────────────────────────
# HUMAN TOUCH: TYPING INDICATOR
# ─────────────────────────────────────────────────────────────────────────────

async def send_typing_indicator(message_sid: str) -> None:
    """
    Uses Twilio Typing Indicators API (Public Beta) to show the typing bubble.
    Also marks the incoming message as read automatically.
    DOCS: https://www.twilio.com/docs/whatsapp/api/typing-indicators-resource
    """
    if not message_sid or not TWILIO_ACCOUNT_SID:
        return
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://messaging.twilio.com/v2/Indicators/Typing.json",
                auth=(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN),
                data={"messageId": message_sid, "channel": "whatsapp"},
                timeout=5.0,
            )
            if resp.status_code == 200:
                logger.info(f"Typing indicator sent for message {message_sid}")
            else:
                logger.warning(f"Typing indicator failed: {resp.status_code} {resp.text}")
    except Exception as e:
        logger.warning(f"Typing indicator error (non-fatal): {e}")


# ─────────────────────────────────────────────────────────────────────────────
# HUMAN TOUCH: BATCH SEND via Twilio REST (multi-message splits)
# ─────────────────────────────────────────────────────────────────────────────

async def send_whatsapp_message(to: str, body: str) -> None:
    """Send a single WhatsApp message via Twilio REST API."""
    if not TWILIO_ACCOUNT_SID:
        logger.warning("Twilio creds not set — cannot send proactive message")
        return
    try:
        from_number = TWILIO_FROM if TWILIO_FROM.startswith("whatsapp:") else f"whatsapp:{TWILIO_FROM}"
        to_number   = to if to.startswith("whatsapp:") else f"whatsapp:{to}"
        async with httpx.AsyncClient() as client:
            await client.post(
                f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_ACCOUNT_SID}/Messages.json",
                auth=(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN),
                data={"From": from_number, "To": to_number, "Body": body},
                timeout=10.0,
            )
    except Exception as e:
        logger.error(f"Failed to send proactive message: {e}")


async def send_batch_messages(to: str, reply_text: str) -> str:
    """
    Split replies on [SPLIT] tag and send each as a separate message with a small
    human-like delay between them. Returns the FIRST part for the TwiML response;
    the rest are sent proactively via REST API so they arrive as separate bubbles.
    """
    parts = [p.strip() for p in reply_text.split("[SPLIT]") if p.strip()]
    if not parts:
        return reply_text

    first_part = parts[0]
    remaining  = parts[1:]

    if remaining:
        async def _send_rest():
            for part in remaining:
                await asyncio.sleep(1.5)  # human-like pause between messages
                await send_whatsapp_message(to, part)
        asyncio.create_task(_send_rest())

    return first_part


# ─────────────────────────────────────────────────────────────────────────────
# HEALTH CHECK
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/")
def health_check():
    return {"status": "Machine 3 Webhook Router is Online"}


# ─────────────────────────────────────────────────────────────────────────────
# MAIN WEBHOOK
# ─────────────────────────────────────────────────────────────────────────────

@app.post("/webhook/whatsapp")
async def whatsapp_webhook(
    request: Request,
    From: str = Form(...),
    Body: str = Form(""),
    MessageSid: str = Form(""),
):
    """
    Twilio posts here when a user replies to our outbound WhatsApp message.
    We intercept it and route it to Machine 3 (LangGraph Sales Agent).
    """
    clean_phone = From.replace("whatsapp:", "").strip()
    logger.info(f"Incoming WhatsApp from {clean_phone}: {Body[:50]}")

    # ── Step 1: Show typing indicator immediately (non-blocking) ──────────
    if MessageSid:
        asyncio.create_task(send_typing_indicator(MessageSid))

    # ── Step 2: Load Machine 1 lead intel ────────────────────────────────
    lead_data = {}
    db_path = "lead_queue.db"

    if os.path.exists(db_path):
        try:
            with sqlite3.connect(db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                phone_for_query = clean_phone.replace("+", "").replace(" ", "")
                cursor.execute(
                    "SELECT * FROM leads WHERE REPLACE(REPLACE(phone, ' ', ''), '+', '') = ?",
                    (phone_for_query,)
                )
                row = cursor.fetchone()
                if row:
                    lead_data = dict(row)
                    logger.info(f"Found lead in DB: {lead_data.get('clinic_name')}")
                    try:
                        from sales_engine import mark_lead_replied
                        mark_lead_replied(clean_phone)
                    except Exception as e:
                        logger.warning(f"Could not mark lead replied: {e}")
        except Exception as e:
            logger.error(f"Error querying lead DB: {e}")

    # ── Step 3: Run LangGraph Sales Agent ─────────────────────────────────
    try:
        reply_text = await run_sales_agent(
            phone=clean_phone,
            user_message=Body,
            lead_data=lead_data,
        )
        logger.info(f"Agent reply: {reply_text[:80]}...")

        # ── Step 4: Update lead status for demo bookings ──────────────────
        if "cal.com" in reply_text.lower() and lead_data:
            try:
                with sqlite3.connect(db_path) as conn:
                    conn.execute(
                        "UPDATE leads SET status = 'DEMO_BOOKED' WHERE phone = ?",
                        (clean_phone,)
                    )
            except Exception:
                pass

    except Exception as e:
        logger.error(f"Agent crashed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        reply_text = "Hey! Catching up on messages — are you free for a quick 10-min call this week?"

    # ── Step 5: Handle batch messages (split on [SPLIT]) ─────────────────
    twiml_reply = await send_batch_messages(clean_phone, reply_text)

    # ── Step 6: Return TwiML with the FIRST message ───────────────────────
    response = MessagingResponse()
    response.message(twiml_reply)
    return PlainTextResponse(str(response), media_type="application/xml")
