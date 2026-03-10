"""
═══════════════════════════════════════════════════════════════════════════════
GRAPH — Lead-OS Sales Agent LangGraph Compilation
═══════════════════════════════════════════════════════════════════════════════
Compiles all nodes into a single LangGraph workflow.
Exposes `run_sales_agent()` as the main entry point for all channels.

Flow:
   ingest_context → detect_intent → draft_response → process_tags → persist
"""

import logging
from typing import Dict, Any, Optional

from .state import SalesAgentState
from .nodes import (
    node_ingest_context,
    node_detect_intent,
    node_draft_response,
    node_process_tags,
    node_persist,
)

logger = logging.getLogger("leados_sales")

# ── Try importing LangGraph ──────────────────────────────────────────────────
try:
    from langgraph.graph import StateGraph, END
    HAS_LANGGRAPH = True
except ImportError:
    HAS_LANGGRAPH = False
    logger.warning("LangGraph not installed. Using fallback sequential pipeline for Sales Agent.")


# ═══════════════════════════════════════════════════════════════════════════════
# GRAPH BUILDER
# ═══════════════════════════════════════════════════════════════════════════════

def _build_graph():
    """Build and compile the LangGraph sales conversation workflow."""
    if not HAS_LANGGRAPH:
        return None

    graph = StateGraph(SalesAgentState)

    graph.add_node("ingest_context",  node_ingest_context)
    graph.add_node("detect_intent",   node_detect_intent)
    graph.add_node("draft_response",  node_draft_response)
    graph.add_node("process_tags",    node_process_tags)
    graph.add_node("persist",         node_persist)

    graph.set_entry_point("ingest_context")
    graph.add_edge("ingest_context", "detect_intent")
    graph.add_edge("detect_intent",  "draft_response")
    graph.add_edge("draft_response", "process_tags")
    graph.add_edge("process_tags",   "persist")
    graph.add_edge("persist",        END)

    return graph.compile()


# Compile once at import time
_compiled_graph = None


def _get_graph():
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = _build_graph()
    return _compiled_graph


# ═══════════════════════════════════════════════════════════════════════════════
# SEQUENTIAL FALLBACK (if LangGraph not installed)
# ═══════════════════════════════════════════════════════════════════════════════

def _run_sequential(state: dict) -> dict:
    """Run all nodes in order without LangGraph."""
    result = {**state}
    for node_fn in [node_ingest_context, node_detect_intent, node_draft_response, node_process_tags, node_persist]:
        updates = node_fn(result)
        result.update(updates or {})
    return result


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN ENTRY POINT — Called by webhooks (WhatsApp, Email, Instagram, etc.)
# ═══════════════════════════════════════════════════════════════════════════════

async def run_sales_agent(
    phone: str,
    user_message: str,
    channel: str = "whatsapp",
    lead_data: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Process one inbound message from a B2B sales lead on any channel.

    Args:
        phone:        Lead phone or unique ID.
        user_message:  The incoming message text.
        channel:       'whatsapp' | 'email' | 'instagram'
        lead_data:     Optional pre-loaded dict from lead_queue.db.

    Returns:
        Reply string (may contain [SPLIT] markers for multi-bubble WhatsApp).
        Returns empty string if the lead is WON/LOST and should not be replied to.
    """
    initial_state = {
        "phone": phone,
        "user_message": user_message,
        "channel": channel,
        "lead_data": lead_data or {},
    }

    graph = _get_graph()
    if graph:
        # LangGraph execution
        result = graph.invoke(initial_state)
    else:
        # Fallback sequential
        result = _run_sequential(initial_state)

    reply = result.get("reply_text", "")
    logger.info(f"[SALES][{channel.upper()}] {phone[-4:]}: stage={result.get('stage')} score={result.get('interest_score')} reply_len={len(reply)}")
    return reply
