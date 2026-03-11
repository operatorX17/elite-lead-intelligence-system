import os
import sqlite3
import logging
from fastapi import FastAPI, Request, Form
from fastapi.responses import PlainTextResponse

# ── Machine 3 — Omnichannel AI Sales Closer ──
from leados_sales import run_sales_agent
from twilio.twiml.messaging_response import MessagingResponse

# Configure structured logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="ZRAI Machine 3 - Twilio Webhook Router")

@app.get("/")
def health_check():
    return {"status": "Machine 3 Webhook Router is Online"}

@app.post("/webhook/whatsapp")
async def whatsapp_webhook(
    From: str = Form(...),
    Body: str = Form(""),
):
    """
    Twilio posts here when a user replies to our outbound WhatsApp message.
    We intercept it and route it to Machine 3 (LangGraph Sales Agent).
    """
    clean_phone = From.replace("whatsapp:", "").strip()
    logger.info(f"Incoming WhatsApp from {clean_phone}: {Body[:50]}")

    lead_data = {}
    db_path = "lead_queue.db"
    
    if os.path.exists(db_path):
        try:
            with sqlite3.connect(db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                # Try to cleanly match phone number ignoring spaces and +
                phone_for_query = clean_phone.replace("+", "").replace(" ", "")
                cursor.execute(
                    "SELECT * FROM leads WHERE REPLACE(REPLACE(phone, ' ', ''), '+', '') = ?", 
                    (phone_for_query,)
                )
                row = cursor.fetchone()
                
                if row:
                    lead_data = dict(row)
                    logger.info(f"Found lead in DB: {lead_data.get('clinic_name')}")
                    
                    # Prevent sales_engine from sending outbound cold-followups to them
                    try:
                        from sales_engine import mark_lead_replied
                        mark_lead_replied(clean_phone)
                    except Exception as e:
                        logger.warning(f"Could not mark lead replied via sales_engine: {e}")
                        
        except Exception as e:
            logger.error(f"Error querying lead DB: {e}")

    # Process via LangGraph Sales Agent
    try:
        reply_text = await run_sales_agent(
            phone=clean_phone,
            user_message=Body,
            lead_data=lead_data,
        )
        logger.info(f"Agent reply generated: {reply_text[:50]}...")
        
        # Check for conversion
        if "cal.com" in reply_text.lower() and lead_data:
            try:
                with sqlite3.connect(db_path) as conn:
                    conn.execute("UPDATE leads SET status = 'DEMO_BOOKED' WHERE phone = ?", (clean_phone,))
            except Exception:
                pass
                
    except Exception as e:
        logger.error(f"Agent crashed: {e}")
        reply_text = "Hey! Happy to answer. Are you free for a 10-min call this week?"

    # Send Twilio TwiML response natively
    response = MessagingResponse()
    response.message(reply_text)
    return PlainTextResponse(str(response), media_type="application/xml")
