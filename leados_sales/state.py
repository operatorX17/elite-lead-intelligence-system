"""
═══════════════════════════════════════════════════════════════════════════════
STATE — Lead-OS Sales Agent Omnichannel State Definition
═══════════════════════════════════════════════════════════════════════════════
Defines the TypedDict used by LangGraph to pass data through every node.
This is the single source of truth for what the agent "knows" mid-conversation.
"""

from typing import Dict, List, Any, Optional
from typing_extensions import TypedDict


class SalesAgentState(TypedDict, total=False):
    """
    The complete state for a single sales conversation.
    Flows through every LangGraph node.
    """

    # ── Identity ──────────────────────────────────────────────────────────────
    phone: str                          # Lead phone (unique key)
    channel: str                        # 'whatsapp' | 'email' | 'instagram'

    # ── Lead Intel (from Machine 1 — Lead-OS Scraper) ─────────────────────────
    lead_data: Dict[str, Any]           # Raw dict from lead_queue.db
    clinic_name: str
    owner_name: str
    city: str
    weakness_summary: str               # AI-identified weakness from scraping
    lead_score: int                     # Machine 1 score (0-100)

    # ── Conversation Memory ──────────────────────────────────────────────────
    messages: List[Dict[str, str]]      # Chat history [{role, content}]
    user_message: str                   # The current inbound message

    # ── Sales Engine State ───────────────────────────────────────────────────
    stage: str                          # QUALIFY | PROBLEM | SOLUTION | OFFER | CLOSE | WON | LOST | HUMAN | NURTURE
    interest_score: int                 # 0-100 engagement/buying signal score
    objections: List[str]               # ["price", "skeptical", "busy"]
    inquiry_volume: Optional[str]       # "20 messages"
    who_handles: Optional[str]          # "receptionist"
    booking_process: Optional[str]      # "phone"
    contact_name: Optional[str]
    business_name: Optional[str]
    business_type: Optional[str]

    # ── Signals (per-turn) ───────────────────────────────────────────────────
    signals: Dict[str, bool]            # Intent detection results for this turn
    score_delta: int                    # Points to add this turn

    # ── Output ───────────────────────────────────────────────────────────────
    reply_text: str                     # Final cleaned reply to send
    raw_llm_output: str                 # Raw LLM output (with tags)

    # ── Events / Flags ───────────────────────────────────────────────────────
    demo_booked: bool
    trial_activated: bool
    payment_sent: bool
    payment_completed: bool
    human_escalation: bool
    should_stop: bool                   # True = don't send a reply (WON/LOST guard)
