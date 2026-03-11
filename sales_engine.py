"""
═══════════════════════════════════════════════════════════════════════════════
AUTONOMOUS AI SALES ENGINE v2.0
═══════════════════════════════════════════════════════════════════════════════
Reads Lead-OS output (leads.json / top_10.json) and runs a LangGraph-based
outreach pipeline: Validate → Email (Resend) → WhatsApp (Meta Cloud API) →
Schedule Follow-ups → Update DB.

Usage:
  python sales_engine.py --import-file "output/.../leads.json"
  python sales_engine.py --process
  python sales_engine.py --process --dry-run
  python sales_engine.py --status
═══════════════════════════════════════════════════════════════════════════════
"""

import os
import sys
import json
import sqlite3
import datetime
import argparse
import hashlib
import logging
import re
from typing import List, Dict, Any, Optional, Annotated
from operator import add
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# ── Windows UTF-8 Fix ────────────────────────────────────────────────────────
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("sales_engine")

# ── Environment ──────────────────────────────────────────────────────────────
RESEND_API_KEY      = os.getenv("RESEND_API_KEY", "")
RESEND_FROM_EMAIL   = os.getenv("RESEND_FROM_EMAIL", "growth@yourdomain.com")
TWILIO_ACCOUNT_SID  = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN   = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER", "")
BOOKING_LINK        = os.getenv("BOOKING_LINK", "https://cal.com/yourname/demo")
OPENROUTER_API_KEY  = os.getenv("OPENROUTER_API_KEY", "")
DB_PATH             = "lead_queue.db"

# ── Try importing LangGraph ──────────────────────────────────────────────────
try:
    from langgraph.graph import StateGraph, END
    from typing_extensions import TypedDict
    HAS_LANGGRAPH = True
except ImportError:
    HAS_LANGGRAPH = False
    logger.warning("LangGraph not installed. Using fallback sequential pipeline.")
    from typing_extensions import TypedDict

# ── Try importing requests ──────────────────────────────────────────────────
try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False
    logger.warning("requests not installed. API calls will be skipped.")


# ═══════════════════════════════════════════════════════════════════════════════
# 1. DATABASE
# ═══════════════════════════════════════════════════════════════════════════════

def init_db():
    """Create the lead_queue.db tables if they don't exist. Also runs safe migrations."""
    # --- Schema migration: add replied_at if missing (safe on existing DBs) ---
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("ALTER TABLE leads ADD COLUMN replied_at TIMESTAMP")
    except Exception:
        pass  # Column already exists — ignore

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS leads (
                lead_id         TEXT PRIMARY KEY,
                clinic_name     TEXT,
                owner_name      TEXT,
                phone           TEXT,
                email           TEXT,
                city            TEXT,
                score           INTEGER,
                tier            TEXT,
                weakness_summary TEXT,
                outreach_angle  TEXT,
                email_subject   TEXT,
                email_body      TEXT,
                whatsapp_msg    TEXT,
                revenue_loss    INTEGER,
                website         TEXT,
                rating          REAL,
                reviews_count   INTEGER,
                status          TEXT DEFAULT 'NEW',
                created_at      TIMESTAMP,
                last_contact    TIMESTAMP,
                replied_at      TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS followups (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                lead_id      TEXT,
                step         INTEGER,
                channel      TEXT,
                scheduled_at TIMESTAMP,
                completed_at TIMESTAMP,
                status       TEXT DEFAULT 'PENDING',
                FOREIGN KEY(lead_id) REFERENCES leads(lead_id)
            );
            CREATE TABLE IF NOT EXISTS outreach_log (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                lead_id    TEXT,
                channel    TEXT,
                status     TEXT,
                detail     TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)


# ═══════════════════════════════════════════════════════════════════════════════
# 2. LEAD IMPORTER
# ═══════════════════════════════════════════════════════════════════════════════

def _safe_json_list(val) -> list:
    """Parse a JSON-encoded list string, or return as-is if already a list."""
    if isinstance(val, list):
        return val
    if isinstance(val, str):
        try:
            parsed = json.loads(val)
            return parsed if isinstance(parsed, list) else [val]
        except (json.JSONDecodeError, TypeError):
            return [val] if val else []
    return []


def _clean_phone(phone: str) -> str:
    """Normalize to digits only, prepend 91 if 10 digits."""
    digits = re.sub(r"\D", "", phone)
    if len(digits) == 10:
        digits = f"91{digits}"
    return digits


def _make_lead_id(name: str) -> str:
    """Deterministic lead ID from clinic name."""
    return hashlib.md5(name.lower().strip().encode()).hexdigest()[:16]


def import_leads(json_file: str) -> int:
    """Read leads.json or top_X.json and insert into the queue DB."""
    path = Path(json_file)
    if not path.exists():
        logger.error(f"File not found: {json_file}")
        return 0

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    leads = data if isinstance(data, list) else data.get("leads", [])

    new_count = 0
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        for lead in leads:
            name = lead.get("business_name", "")
            if not name:
                continue

            lead_id = lead.get("lead_id") or _make_lead_id(name)
            score = lead.get("score", lead.get("final_score", 0))

            # Extract contacts from rich leads.json format
            phones = _safe_json_list(lead.get("phones", []))
            emails = _safe_json_list(lead.get("emails", []))
            # Filter out junk emails (image filenames etc.)
            emails = [e for e in emails if "@" in e and not e.endswith(".png")]

            primary_phone = phones[0] if phones else lead.get("phone", "")
            primary_email = emails[0] if emails else ""

            # Parse weaknesses for summary
            weakness_list = _safe_json_list(lead.get("weaknesses", []))
            weakness_summary = "\n".join(
                [f"- {w.split(': ', 1)[-1]}" for w in weakness_list[:3]]
            )

            try:
                cursor.execute("""
                    INSERT OR IGNORE INTO leads (
                        lead_id, clinic_name, owner_name, phone, email, city,
                        score, tier, weakness_summary, outreach_angle,
                        email_subject, email_body, whatsapp_msg,
                        revenue_loss, website, rating, reviews_count,
                        status, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    lead_id,
                    name,
                    lead.get("doctor_name") or lead.get("owner_name", ""),
                    primary_phone,
                    primary_email,
                    lead.get("city", ""),
                    score,
                    lead.get("tier", ""),
                    weakness_summary,
                    lead.get("outreach_angle", ""),
                    lead.get("email_subject", f"Quick question about {name}"),
                    lead.get("email_body", ""),
                    lead.get("whatsapp_msg", ""),
                    lead.get("revenue_loss", lead.get("estimated_revenue_loss", 0)),
                    lead.get("website", ""),
                    lead.get("rating", 0),
                    lead.get("reviews", lead.get("reviews_count", 0)),
                    "NEW",
                    datetime.datetime.now().isoformat(),
                ))
                if cursor.rowcount > 0:
                    new_count += 1
            except Exception as e:
                logger.warning(f"Skipping {name}: {e}")
    logger.info(f"Imported {new_count} new leads into queue (skipped {len(leads) - new_count} existing).")
    return new_count


# ═══════════════════════════════════════════════════════════════════════════════
# 3. LANGGRAPH STATE & NODES
# ═══════════════════════════════════════════════════════════════════════════════

class SalesState(TypedDict):
    # Lead record fields
    lead_id: str
    clinic_name: str
    owner_name: str
    phone: str
    email: str
    city: str
    score: int
    tier: str
    weakness_summary: str
    outreach_angle: str
    email_subject: str
    email_body: str
    whatsapp_msg: str
    revenue_loss: int
    website: str
    rating: float
    reviews_count: int
    # Execution tracking
    is_valid: bool
    email_sent: bool
    whatsapp_sent: bool
    followups_scheduled: bool
    dry_run: bool
    errors: Annotated[list, add]


# ── Node: Validate ───────────────────────────────────────────────────────────

def node_validate(state: SalesState) -> dict:
    """Check if the lead has valid contact info and meets score threshold."""
    lead_id = state["lead_id"]
    errors = []

    if state["score"] < 55:
        errors.append(f"Score {state['score']} below threshold 55")
    if not state["phone"] and not state["email"]:
        errors.append("No contactable phone or email")

    is_valid = len(errors) == 0
    if is_valid:
        logger.info(f"  [{lead_id}] VALID — Score: {state['score']}, Phone: {'Yes' if state['phone'] else 'No'}, Email: {'Yes' if state['email'] else 'No'}")
    else:
        logger.warning(f"  [{lead_id}] INVALID — {', '.join(errors)}")

    return {"is_valid": is_valid, "errors": errors}


# ── Node: Send Email ─────────────────────────────────────────────────────────

def node_send_email(state: SalesState) -> dict:
    """Send personalized cold email via Resend API."""
    if not state["email"]:
        logger.info(f"  [{state['lead_id']}] No email address, skipping email.")
        return {"email_sent": False}

    if state["dry_run"]:
        logger.info(f"  [{state['lead_id']}] [DRY-RUN] Would send email to {state['email']}")
        _log_outreach(state["lead_id"], "email", "DRY_RUN", f"To: {state['email']}")
        return {"email_sent": True}

    if not RESEND_API_KEY or not HAS_REQUESTS:
        logger.warning(f"  [{state['lead_id']}] RESEND_API_KEY not configured. Skipping email.")
        return {"email_sent": False}

    # Use pre-generated email from Lead-OS
    body = state["email_body"]
    if not body:
        body = f"""Hi,

We noticed {state['clinic_name']} ({state['reviews_count']} Google reviews) has some gaps in online booking and patient capture.

{state['outreach_angle']}

Would you like to see a quick demo of how we fix this?

Book a 10-minute demo: {BOOKING_LINK}

Best,
[Your Name]"""

    # Replace placeholder
    body = body.replace("[Your Name]", "Sai Prakash")

    payload = {
        "from": RESEND_FROM_EMAIL,
        "to": [state["email"]],
        "subject": state["email_subject"] or f"Quick insight about {state['clinic_name']}",
        "html": body.replace("\n", "<br>"),
    }

    try:
        resp = requests.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {RESEND_API_KEY}", "Content-Type": "application/json"},
            json=payload,
            timeout=15,
        )
        if resp.status_code in (200, 201):
            logger.info(f"  [{state['lead_id']}] EMAIL SENT to {state['email']}")
            _log_outreach(state["lead_id"], "email", "SENT", f"To: {state['email']}")
            return {"email_sent": True}
        else:
            detail = resp.text[:200]
            logger.error(f"  [{state['lead_id']}] Email failed ({resp.status_code}): {detail}")
            _log_outreach(state["lead_id"], "email", "FAILED", detail)
            return {"email_sent": False, "errors": [f"Email {resp.status_code}: {detail}"]}
    except Exception as e:
        logger.error(f"  [{state['lead_id']}] Email exception: {e}")
        _log_outreach(state["lead_id"], "email", "ERROR", str(e))
        return {"email_sent": False, "errors": [f"Email error: {e}"]}


# ── Node: Send WhatsApp ──────────────────────────────────────────────────────

def node_send_whatsapp(state: SalesState) -> dict:
    """Send WhatsApp message via Meta Cloud API."""
    if not state["phone"]:
        logger.info(f"  [{state['lead_id']}] No phone number, skipping WhatsApp.")
        return {"whatsapp_sent": False}

    clean_phone = _clean_phone(state["phone"])
    if len(clean_phone) < 10:
        logger.warning(f"  [{state['lead_id']}] Invalid phone: {state['phone']}")
        return {"whatsapp_sent": False}

    if state["dry_run"]:
        logger.info(f"  [{state['lead_id']}] [DRY-RUN] Would send WhatsApp to {clean_phone}")
        _log_outreach(state["lead_id"], "whatsapp", "DRY_RUN", f"To: {clean_phone}")
        return {"whatsapp_sent": True}

    if not TWILIO_ACCOUNT_SID or not TWILIO_AUTH_TOKEN or not TWILIO_PHONE_NUMBER or not HAS_REQUESTS:
        logger.warning(f"  [{state['lead_id']}] Twilio API not configured. Skipping.")
        return {"whatsapp_sent": False}

    # Format the Twilio destination number
    to_whatsapp = f"whatsapp:+{clean_phone}"
    from_whatsapp = f"whatsapp:{TWILIO_PHONE_NUMBER.replace('whatsapp:', '')}"

    # Use pre-generated message from Lead-OS
    message = state["whatsapp_msg"]
    if not message:
        message = f"""Hi! Quick note about {state['clinic_name']}.

{state['outreach_angle']}

Would you like to see how we fix this?
Book a 10-min demo: {BOOKING_LINK}"""

    # ── The Twilio Sales Outreach Template ──────────────────────────────────────
    CONTENT_SID = "HX348cc7496c771dd8f7e7fa27d81a0764"
    
    # We pass the doctor's name (or clinic name if owner name missing) and the weakness
    name_to_use = state.get("owner_name") if state.get("owner_name") else state.get("clinic_name", "Doctor")
    weakness_to_use = state.get("weakness_summary") if state.get("weakness_summary") else "your patient booking process"

    payload = {
        "To": to_whatsapp,
        "From": from_whatsapp,
        "ContentSid": CONTENT_SID,
        "ContentVariables": json.dumps({
            "1": name_to_use,       # Hi Dr. {{1}}
            "2": weakness_to_use    # Quick question about {{2}}
        })
    }

    try:
        url = f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_ACCOUNT_SID}/Messages.json"
        
        resp = requests.post(
            url,
            auth=(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN),
            data=payload,
            timeout=15,
        )
        if resp.status_code in (200, 201):
            logger.info(f"  [{state['lead_id']}] WHATSAPP SENT via Twilio to {clean_phone}")
            _log_outreach(state["lead_id"], "whatsapp", "SENT", f"To: {clean_phone}")
            return {"whatsapp_sent": True}
        else:
            detail = resp.text[:200]
            logger.error(f"  [{state['lead_id']}] WhatsApp failed ({resp.status_code}): {detail}")
            _log_outreach(state["lead_id"], "whatsapp", "FAILED", detail)
            return {"whatsapp_sent": False, "errors": [f"WA {resp.status_code}: {detail}"]}
    except Exception as e:
        logger.error(f"  [{state['lead_id']}] WhatsApp exception: {e}")
        _log_outreach(state["lead_id"], "whatsapp", "ERROR", str(e))
        return {"whatsapp_sent": False, "errors": [f"WA error: {e}"]}

def _send_whatsapp_text(state: SalesState, clean_phone: str, message: str) -> dict:
    """Fallback: Not really needed for Twilio since Twilio routes text to templates, but keeping interface intact."""
    to_whatsapp = f"whatsapp:+{clean_phone}"
    from_whatsapp = f"whatsapp:{TWILIO_PHONE_NUMBER.replace('whatsapp:', '')}"
    
    payload = {
        "To": to_whatsapp,
        "From": from_whatsapp,
        "Body": message
    }
    try:
        url = f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_ACCOUNT_SID}/Messages.json"
        resp = requests.post(
            url,
            auth=(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN),
            data=payload,
            timeout=15,
        )
        if resp.status_code in (200, 201):
            logger.info(f"  [{state['lead_id']}] WHATSAPP TEXT SENT via Twilio to {clean_phone}")
            _log_outreach(state["lead_id"], "whatsapp_text", "SENT", f"To: {clean_phone}")
            return {"whatsapp_sent": True}
        else:
            detail = resp.text[:200]
            logger.error(f"  [{state['lead_id']}] WA text failed: {detail}")
            _log_outreach(state["lead_id"], "whatsapp_text", "FAILED", detail)
            return {"whatsapp_sent": False}
    except Exception as e:
        return {"whatsapp_sent": False, "errors": [f"WA text error: {e}"]}


# ── Node: Schedule Follow-ups ────────────────────────────────────────────────

def node_schedule_followups(state: SalesState) -> dict:
    """Schedule Day 2, Day 5, Day 9 follow-ups."""
    if not state.get("email_sent") and not state.get("whatsapp_sent"):
        return {"followups_scheduled": False}

    lead_id = state["lead_id"]
    now = datetime.datetime.now()

    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        # Check if followups already exist
        cursor.execute("SELECT COUNT(*) FROM followups WHERE lead_id = ?", (lead_id,))
        if cursor.fetchone()[0] > 0:
            logger.info(f"  [{lead_id}] Follow-ups already scheduled, skipping.")
            return {"followups_scheduled": True}

        for day, channel in [(2, "email"), (2, "whatsapp"), (5, "email"), (5, "whatsapp"), (9, "email")]:
            cursor.execute("""
                INSERT INTO followups (lead_id, step, channel, scheduled_at, status)
                VALUES (?, ?, ?, ?, 'PENDING')
            """, (lead_id, day, channel, (now + datetime.timedelta(days=day)).isoformat()))
        conn.commit()

    logger.info(f"  [{lead_id}] Scheduled 5 follow-ups (Day 2, 5, 9)")
    return {"followups_scheduled": True}


# ── Node: Update Status ──────────────────────────────────────────────────────

def node_update_status(state: SalesState) -> dict:
    """Mark lead as CONTACTED or FAILED in the queue DB."""
    lead_id = state["lead_id"]
    contacted = state.get("email_sent") or state.get("whatsapp_sent")
    new_status = "CONTACTED" if contacted else "FAILED"

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            UPDATE leads SET status = ?, last_contact = ? WHERE lead_id = ?
        """, (new_status, datetime.datetime.now().isoformat(), lead_id))
        conn.commit()

    logger.info(f"  [{lead_id}] Status → {new_status}")
    return {}


# ── Outreach Logger ──────────────────────────────────────────────────────────

def mark_lead_replied(phone: str):
    """Called by api.py when a prospect replies to any message.
    Sets replied_at and status=REPLIED so follow-ups stop immediately."""
    clean = re.sub(r"\D", "", phone)
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("""
                UPDATE leads
                SET status = 'REPLIED',
                    replied_at = ?
                WHERE REPLACE(REPLACE(phone, ' ', ''), '+', '') = ?
                  AND replied_at IS NULL
            """, (datetime.datetime.now().isoformat(), clean))
            # Also cancel any pending followups for this lead
            conn.execute("""
                UPDATE followups SET status = 'CANCELLED'
                WHERE lead_id = (
                    SELECT lead_id FROM leads
                    WHERE REPLACE(REPLACE(phone, ' ', ''), '+', '') = ?
                )
                AND status = 'PENDING'
            """, (clean,))
            conn.commit()
            logger.info(f"[REPLIED] Lead marked replied + followups cancelled: {clean[-4:]}")
    except Exception as e:
        logger.warning(f"mark_lead_replied error: {e}")


def _log_outreach(lead_id: str, channel: str, status: str, detail: str = ""):
    """Log every outreach attempt for audit trail."""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("""
                INSERT INTO outreach_log (lead_id, channel, status, detail, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (lead_id, channel, status, detail, datetime.datetime.now().isoformat()))
            conn.commit()
    except Exception:
        pass


# ═══════════════════════════════════════════════════════════════════════════════
# 4. GRAPH BUILDER
# ═══════════════════════════════════════════════════════════════════════════════

def _route_after_validate(state: SalesState) -> str:
    return "send_email" if state["is_valid"] else "update_status"


def build_graph():
    """Build and compile the LangGraph outreach workflow."""
    if not HAS_LANGGRAPH:
        return None

    graph = StateGraph(SalesState)

    graph.add_node("validate", node_validate)
    graph.add_node("send_email", node_send_email)
    graph.add_node("send_whatsapp", node_send_whatsapp)
    graph.add_node("schedule_followups", node_schedule_followups)
    graph.add_node("update_status", node_update_status)

    graph.set_entry_point("validate")
    graph.add_conditional_edges("validate", _route_after_validate, {
        "send_email": "send_email",
        "update_status": "update_status",
    })
    graph.add_edge("send_email", "send_whatsapp")
    graph.add_edge("send_whatsapp", "schedule_followups")
    graph.add_edge("schedule_followups", "update_status")
    graph.add_edge("update_status", END)

    return graph.compile()


# ═══════════════════════════════════════════════════════════════════════════════
# 5. SEQUENTIAL FALLBACK (if LangGraph not installed)
# ═══════════════════════════════════════════════════════════════════════════════

def run_sequential_pipeline(state: SalesState) -> SalesState:
    """Run all nodes in order without LangGraph."""
    result = {**state}
    for node_fn in [node_validate, node_send_email, node_send_whatsapp, node_schedule_followups, node_update_status]:
        if node_fn == node_send_email and not result.get("is_valid"):
            continue
        if node_fn == node_send_whatsapp and not result.get("is_valid"):
            continue
        if node_fn == node_schedule_followups and not result.get("is_valid"):
            continue
        update = node_fn(result)
        result.update(update)
    return result


# ═══════════════════════════════════════════════════════════════════════════════
# 6. FOLLOW-UP PROCESSOR
# ═══════════════════════════════════════════════════════════════════════════════

def run_followups(dry_run: bool = False):
    """Process pending follow-ups that are overdue."""
    logger.info("Checking for due follow-ups...")

    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("""
            SELECT f.id, f.lead_id, f.step, f.channel,
                   l.clinic_name, l.owner_name, l.phone, l.email,
                   l.outreach_angle, l.weakness_summary
            FROM followups f
            JOIN leads l ON f.lead_id = l.lead_id
            WHERE f.status = 'PENDING'
              AND f.scheduled_at <= ?
              AND l.status = 'CONTACTED'
              AND l.replied_at IS NULL
        """, (datetime.datetime.now().isoformat(),))

        due = cursor.fetchall()
        if not due:
            logger.info("No follow-ups due right now.")
            return

        logger.info(f"Processing {len(due)} due follow-ups...")

        for row in due:
            f_id = row["id"]
            lead_id = row["lead_id"]
            step = row["step"]
            channel = row["channel"]
            clinic = row["clinic_name"]
            owner = row["owner_name"] or "there"
            phone = row["phone"]
            email = row["email"]
            angle = row["outreach_angle"]

            logger.info(f"  Follow-up Day {step} | {channel.upper()} | {clinic}")

            if dry_run:
                target = email if channel == "email" else _clean_phone(phone) if phone else "N/A"
                logger.info(f"    [DRY-RUN] Would send {channel} follow-up to {target}")
                _log_outreach(lead_id, f"followup_{channel}_d{step}", "DRY_RUN", f"To: {target}")
            else:
                if channel == "email" and email and RESEND_API_KEY and HAS_REQUESTS:
                    followup_subject = f"Following up — {clinic}"
                    followup_body = f"""Hi {owner},

Just floating this to the top of your inbox.

{angle}

Would a quick 10-minute demo be useful? I can walk you through exactly how we recover that revenue.

{BOOKING_LINK}

Best,
Sai Prakash"""
                    try:
                        resp = requests.post("https://api.resend.com/emails", headers={
                            "Authorization": f"Bearer {RESEND_API_KEY}",
                            "Content-Type": "application/json"
                        }, json={
                            "from": RESEND_FROM_EMAIL,
                            "to": [email],
                            "subject": followup_subject,
                            "html": followup_body.replace("\n", "<br>"),
                        }, timeout=15)
                        status = "SENT" if resp.status_code in (200, 201) else "FAILED"
                        _log_outreach(lead_id, f"followup_email_d{step}", status, resp.text[:100])
                    except Exception as e:
                        _log_outreach(lead_id, f"followup_email_d{step}", "ERROR", str(e))

                elif channel == "whatsapp" and phone and TWILIO_ACCOUNT_SID and HAS_REQUESTS:
                    clean = _clean_phone(phone)
                    msg = f"Hi {owner}, just checking in about {clinic}. {angle} Want a quick demo? {BOOKING_LINK}"
                    
                    to_whatsapp = f"whatsapp:+{clean}"
                    from_whatsapp = f"whatsapp:{TWILIO_PHONE_NUMBER.replace('whatsapp:', '')}"
                    
                    try:
                        url = f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_ACCOUNT_SID}/Messages.json"
                        resp = requests.post(
                            url,
                            auth=(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN),
                            data={"To": to_whatsapp, "From": from_whatsapp, "Body": msg},
                            timeout=15,
                        )
                        status = "SENT" if resp.status_code in (200, 201) else "FAILED"
                        _log_outreach(lead_id, f"followup_wa_d{step}", status, resp.text[:100])
                    except Exception as e:
                        _log_outreach(lead_id, f"followup_wa_d{step}", "ERROR", str(e))

            # Update followup as completed
            cursor.execute("UPDATE followups SET status = 'COMPLETED', completed_at = ? WHERE id = ?",
                           (datetime.datetime.now().isoformat(), f_id))
            cursor.execute("UPDATE leads SET last_contact = ? WHERE lead_id = ?",
                           (datetime.datetime.now().isoformat(), lead_id))

        conn.commit()
    logger.info(f"Processed {len(due)} follow-ups.")


# ═══════════════════════════════════════════════════════════════════════════════
# 7. CAMPAIGN RUNNER
# ═══════════════════════════════════════════════════════════════════════════════

def run_campaign(dry_run: bool = False):
    """Process all NEW leads through the outreach pipeline."""
    logger.info("=" * 60)
    logger.info("AUTONOMOUS SALES ENGINE v2.0 — Starting Campaign")
    logger.info("=" * 60)

    graph = build_graph()

    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM leads WHERE status = 'NEW' ORDER BY score DESC")
        records = cursor.fetchall()

    if not records:
        logger.info("No NEW leads in queue. Import some first with --import-file.")
        return

    logger.info(f"Processing {len(records)} NEW leads...")
    results = {"contacted": 0, "failed": 0, "emails_sent": 0, "wa_sent": 0}

    for row in records:
        lead = dict(row)
        clinic = lead["clinic_name"]
        logger.info(f"\n{'─' * 50}")
        logger.info(f"Processing: {clinic} (Score: {lead['score']}, Tier: {lead['tier']})")

        initial_state: SalesState = {
            "lead_id": lead["lead_id"],
            "clinic_name": clinic,
            "owner_name": lead["owner_name"] or "",
            "phone": lead["phone"] or "",
            "email": lead["email"] or "",
            "city": lead["city"] or "",
            "score": lead["score"] or 0,
            "tier": lead["tier"] or "",
            "weakness_summary": lead["weakness_summary"] or "",
            "outreach_angle": lead["outreach_angle"] or "",
            "email_subject": lead["email_subject"] or "",
            "email_body": lead["email_body"] or "",
            "whatsapp_msg": lead["whatsapp_msg"] or "",
            "revenue_loss": lead["revenue_loss"] or 0,
            "website": lead["website"] or "",
            "rating": lead["rating"] or 0,
            "reviews_count": lead["reviews_count"] or 0,
            "is_valid": False,
            "email_sent": False,
            "whatsapp_sent": False,
            "followups_scheduled": False,
            "dry_run": dry_run,
            "errors": [],
        }

        # Execute through LangGraph or fallback
        if graph:
            final = graph.invoke(initial_state)
        else:
            final = run_sequential_pipeline(initial_state)

        # Track results
        if final.get("email_sent") or final.get("whatsapp_sent"):
            results["contacted"] += 1
        else:
            results["failed"] += 1
        if final.get("email_sent"):
            results["emails_sent"] += 1
        if final.get("whatsapp_sent"):
            results["wa_sent"] += 1

    # Run follow-ups too
    logger.info(f"\n{'─' * 50}")
    run_followups(dry_run=dry_run)

    # Summary
    logger.info(f"\n{'=' * 60}")
    logger.info(f"CAMPAIGN COMPLETE")
    logger.info(f"  Leads processed: {len(records)}")
    logger.info(f"  Contacted:       {results['contacted']}")
    logger.info(f"  Failed:          {results['failed']}")
    logger.info(f"  Emails sent:     {results['emails_sent']}")
    logger.info(f"  WhatsApps sent:  {results['wa_sent']}")
    logger.info(f"{'=' * 60}")


# ═══════════════════════════════════════════════════════════════════════════════
# 8. STATUS REPORTER
# ═══════════════════════════════════════════════════════════════════════════════

def show_status():
    """Print the current state of the lead queue."""
    if not Path(DB_PATH).exists():
        logger.info("No lead_queue.db found. Import leads first.")
        return

    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()

        cursor.execute("SELECT status, COUNT(*) FROM leads GROUP BY status")
        statuses = cursor.fetchall()

        cursor.execute("SELECT COUNT(*) FROM followups WHERE status = 'PENDING'")
        pending_followups = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM outreach_log")
        total_outreach = cursor.fetchone()[0]

    print("\n" + "=" * 50)
    print("SALES ENGINE — Queue Status")
    print("=" * 50)
    for status, count in statuses:
        print(f"  {status:12s} : {count}")
    print(f"  {'PENDING FU':12s} : {pending_followups}")
    print(f"  {'TOTAL LOGS':12s} : {total_outreach}")
    print("=" * 50)


# ═══════════════════════════════════════════════════════════════════════════════
# 9. CLI
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Autonomous AI Sales Engine v2.0",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python sales_engine.py --import-file "output/.../leads.json"
  python sales_engine.py --process --dry-run
  python sales_engine.py --process
  python sales_engine.py --status
        """,
    )
    parser.add_argument("--import-file", type=str, help="Path to leads.json or top_X.json to import")
    parser.add_argument("--process", action="store_true", help="Run the outbound campaign on NEW leads")
    parser.add_argument("--followups", action="store_true", help="Process pending follow-ups only")
    parser.add_argument("--dry-run", action="store_true", help="Log everything but don't actually send")
    parser.add_argument("--status", action="store_true", help="Show current queue status")
    args = parser.parse_args()

    # Always init DB
    init_db()

    if args.import_file:
        import_leads(args.import_file)

    if args.process:
        run_campaign(dry_run=args.dry_run)
    elif args.followups:
        run_followups(dry_run=args.dry_run)

    if args.status:
        show_status()

    if not any([args.import_file, args.process, args.followups, args.status]):
        parser.print_help()


if __name__ == "__main__":
    main()
