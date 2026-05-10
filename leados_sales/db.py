"""
═══════════════════════════════════════════════════════════════════════════════
DB — Lead-OS Sales Agent Persistent Memory
═══════════════════════════════════════════════════════════════════════════════
All SQLite operations for conversation history, state, and event logging.
Uses sales_conversations.db in the project root.
"""

import os
import json
import sqlite3
from typing import Dict, Any, List
from datetime import datetime

# Database lives at the project root, alongside lead_queue.db
_SALES_DB = os.path.join(os.path.dirname(os.path.dirname(__file__)), "sales_conversations.db")


# ═══════════════════════════════════════════════════════════════════════════════
# SCHEMA & MIGRATIONS
# ═══════════════════════════════════════════════════════════════════════════════

def init_db():
    """Create tables if they don't exist. Safe to call on every request."""
    with sqlite3.connect(_SALES_DB) as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS sales_history (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                phone       TEXT,
                channel     TEXT DEFAULT 'whatsapp',
                role        TEXT,
                content     TEXT,
                created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS sales_state (
                phone               TEXT PRIMARY KEY,
                stage               TEXT DEFAULT 'QUALIFY',
                interest_score      INTEGER DEFAULT 0,
                business_name       TEXT,
                business_type       TEXT,
                contact_name        TEXT,
                city                TEXT,
                inquiry_volume      TEXT,
                who_handles         TEXT,
                booking_process     TEXT,
                objections          TEXT DEFAULT '[]',
                human_escalation    INTEGER DEFAULT 0,
                demo_booked         INTEGER DEFAULT 0,
                payment_sent        INTEGER DEFAULT 0,
                payment_completed   INTEGER DEFAULT 0,
                trial_activated     INTEGER DEFAULT 0,
                notes               TEXT DEFAULT '',
                updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS sales_events (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                phone       TEXT,
                event       TEXT,
                detail      TEXT,
                created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        # Safe migrations for older DBs
        for col, typedef in [
            ("inquiry_volume", "TEXT"), ("who_handles", "TEXT"),
            ("booking_process", "TEXT"), ("human_escalation", "INTEGER DEFAULT 0"),
            ("payment_sent", "INTEGER DEFAULT 0"), ("trial_activated", "INTEGER DEFAULT 0"),
            ("interest_score", "INTEGER DEFAULT 0"), ("channel", "TEXT DEFAULT 'whatsapp'"),
        ]:
            try:
                conn.execute(f"ALTER TABLE sales_state ADD COLUMN {col} {typedef}")
            except Exception:
                pass
        # Migration for history table channel column
        try:
            conn.execute("ALTER TABLE sales_history ADD COLUMN channel TEXT DEFAULT 'whatsapp'")
        except Exception:
            pass


# ═══════════════════════════════════════════════════════════════════════════════
# STATE CRUD
# ═══════════════════════════════════════════════════════════════════════════════

def load_state(phone: str) -> Dict[str, Any]:
    """Load or create a conversation state for a lead."""
    init_db()
    with sqlite3.connect(_SALES_DB) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM sales_state WHERE phone = ?", (phone,)).fetchone()
        if row:
            d = dict(row)
            try:
                d["objections"] = json.loads(d.get("objections") or "[]")
            except Exception:
                d["objections"] = []
            return d
        # New lead — create fresh record
        conn.execute("INSERT OR IGNORE INTO sales_state (phone) VALUES (?)", (phone,))
        conn.commit()
        return {"phone": phone, "stage": "QUALIFY", "interest_score": 0, "objections": []}


def save_state(phone: str, updates: Dict[str, Any]):
    """Persist state updates for a lead."""
    if "objections" in updates and isinstance(updates["objections"], list):
        updates["objections"] = json.dumps(updates["objections"])
    updates["updated_at"] = datetime.now().isoformat()
    cols = ", ".join(f"{k} = ?" for k in updates)
    vals = list(updates.values()) + [phone]
    with sqlite3.connect(_SALES_DB) as conn:
        conn.execute(f"UPDATE sales_state SET {cols} WHERE phone = ?", vals)
        conn.commit()


# ═══════════════════════════════════════════════════════════════════════════════
# MESSAGE HISTORY
# ═══════════════════════════════════════════════════════════════════════════════

def load_history(phone: str, limit: int = 12) -> List[Dict[str, str]]:
    """Load the last N messages for a lead (across all channels)."""
    with sqlite3.connect(_SALES_DB) as conn:
        rows = conn.execute(
            "SELECT role, content FROM sales_history WHERE phone = ? ORDER BY id DESC LIMIT ?",
            (phone, limit)
        ).fetchall()
    return [{"role": r[0], "content": r[1]} for r in reversed(rows)]


def save_message(phone: str, role: str, content: str, channel: str = "whatsapp"):
    """Save a single message to history."""
    with sqlite3.connect(_SALES_DB) as conn:
        conn.execute(
            "INSERT INTO sales_history (phone, role, content, channel) VALUES (?, ?, ?, ?)",
            (phone, role, content, channel)
        )
        conn.commit()


# ═══════════════════════════════════════════════════════════════════════════════
# EVENT LOG
# ═══════════════════════════════════════════════════════════════════════════════

def log_event(phone: str, event: str, detail: str = ""):
    """Log a sales event (DEMO_BOOKED, PAYMENT_COMPLETED, etc.)."""
    with sqlite3.connect(_SALES_DB) as conn:
        conn.execute(
            "INSERT INTO sales_events (phone, event, detail) VALUES (?, ?, ?)",
            (phone, event, detail)
        )
        conn.commit()


# ═══════════════════════════════════════════════════════════════════════════════
# LEAD DATA FROM Machine 1 (lead_queue.db)
# ═══════════════════════════════════════════════════════════════════════════════

_LEAD_QUEUE_DB = os.path.join(os.path.dirname(os.path.dirname(__file__)), "lead_queue.db")


def load_lead_data(phone: str) -> Dict[str, Any]:
    """
    Pull intel gathered by Machine 1 (Lead-OS scraper) from lead_queue.db.
    Returns clinic name, weakness, score, etc. so the agent can personalize.
    """
    import re
    clean = re.sub(r"\D", "", phone)
    try:
        with sqlite3.connect(_LEAD_QUEUE_DB) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM leads WHERE REPLACE(REPLACE(phone, ' ', ''), '+', '') = ?",
                (clean,)
            ).fetchone()
            if row:
                return dict(row)
    except Exception:
        pass
    return {}
