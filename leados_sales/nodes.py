"""
═══════════════════════════════════════════════════════════════════════════════
NODES — Lead-OS Sales Agent LangGraph Node Functions
═══════════════════════════════════════════════════════════════════════════════
Each function is a LangGraph node. They run in sequence through the graph:

  ingest_context → detect_intent → draft_response → process_tags → persist

Every node reads from and writes to the SalesAgentState TypedDict.
"""

import re
import os
import openai
from typing import Dict, Any, Optional

from .state import SalesAgentState
from .prompts import build_system_prompt, get_fallback
from . import db


# ═══════════════════════════════════════════════════════════════════════════════
# LLM CLIENT (self-contained — zero circular imports)
# ═══════════════════════════════════════════════════════════════════════════════

_client = None


def _get_client():
    global _client
    if _client is None:
        api_key  = os.getenv("OPENAI_API_KEY") or os.getenv("HEALTHCARE_LLM_API_KEY", "")
        base_url = os.getenv("HEALTHCARE_LLM_BASE_URL") or None
        _client  = openai.OpenAI(api_key=api_key, base_url=base_url) if base_url else openai.OpenAI(api_key=api_key)
    return _client


def _model() -> str:
    return os.getenv("HEALTHCARE_LLM_MODEL", os.getenv("LLM_MODEL", "gpt-4o-mini"))


# ═══════════════════════════════════════════════════════════════════════════════
# NODE 1: INGEST CONTEXT
# ═══════════════════════════════════════════════════════════════════════════════

def node_ingest_context(state: dict) -> dict:
    """
    Load conversation state + history + Machine 1 lead data from the databases.
    Populates the state dict with everything the agent needs.
    """
    phone = state["phone"]
    channel = state.get("channel", "whatsapp")

    # Load persistent state
    saved = db.load_state(phone)
    # Load chat history
    history = db.load_history(phone, limit=12)
    # Load Machine 1 intel (lead_queue.db)
    lead_data = state.get("lead_data") or db.load_lead_data(phone)

    stage = saved.get("stage", "QUALIFY")

    # Guard: stop responding to LOST leads
    should_stop = False
    if stage == "LOST":
        should_stop = True
    if stage == "WON" and len(history) > 2:
        should_stop = True

    return {
        "stage": stage,
        "interest_score": saved.get("interest_score", 0),
        "objections": saved.get("objections", []) or [],
        "inquiry_volume": saved.get("inquiry_volume"),
        "who_handles": saved.get("who_handles"),
        "booking_process": saved.get("booking_process"),
        "contact_name": saved.get("contact_name"),
        "business_name": saved.get("business_name"),
        "business_type": saved.get("business_type"),
        "messages": history,
        "lead_data": lead_data,
        # ── Resolved identity fields (merge DB + saved state) ──
        "clinic_name": lead_data.get("clinic_name") or saved.get("business_name") or "",
        "owner_name":  lead_data.get("owner_name")  or saved.get("contact_name") or "",
        "city":        lead_data.get("city")         or saved.get("city") or "",
        # ── Machine 1 intelligence signals ──
        "weakness_summary": lead_data.get("weakness_summary") or saved.get("weakness_summary") or "",
        "lead_score":    lead_data.get("score", 0),
        "website":       lead_data.get("website", ""),
        "google_rating": lead_data.get("google_rating", ""),
        "review_count":  lead_data.get("review_count", ""),
        "missing_phone": lead_data.get("missing_phone", 0),
        "missing_hours": lead_data.get("missing_hours", 0),
        "slow_response": lead_data.get("slow_response", 0),
        "category":      lead_data.get("category", "") or lead_data.get("business_type", ""),
        "channel": channel,
        "should_stop": should_stop,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# NODE 2: DETECT INTENT
# ═══════════════════════════════════════════════════════════════════════════════

def node_detect_intent(state: dict) -> dict:
    """
    Analyze the incoming message for buying signals, objections, and escalation.
    Updates interest_score and objections list.
    """
    if state.get("should_stop"):
        return {}

    msg = state.get("user_message", "").lower()

    signals = {
        "asks_price":      any(w in msg for w in ["cost", "price", "how much", "kitna", "fee", "charge", "rates"]),
        "asks_demo":       any(w in msg for w in ["demo", "show me", "see it", "try", "dekh", "dikha"]),
        "asks_setup":      any(w in msg for w in ["setup", "install", "how long", "time", "start", "begin", "when"]),
        "asks_how_start":  any(w in msg for w in ["how do i", "how to", "kaise", "start kar", "activate", "sign up"]),
        "asks_trial":      any(w in msg for w in ["trial", "test", "free trial", "try it first", "demo account"]),
        "ready_to_buy":    any(w in msg for w in ["yes", "okay", "ok", "done", "let's go", "proceed", "haan", "chalega", "book it", "send link"]),
        "wants_human":     any(w in msg for w in ["speak", "call me", "founder", "talk to", "human", "person", "manager", "owner"]),
        "price_objection": any(w in msg for w in ["expensive", "costly", "too much", "mahanga", "budget", "can't afford", "not affordable"]),
        "skeptical":       any(w in msg for w in ["not sure", "doubt", "really", "actually work", "does it work", "fake", "scam", "trust"]),
        "busy":            any(w in msg for w in ["busy", "later", "not now", "some other time", "remind", "next week", "abhi nahi"]),
        "not_interested":  any(w in msg for w in ["no thanks", "not interested", "nahi chahiye", "don't need", "stop"]),
        "positive":        any(w in msg for w in ["interesting", "sounds good", "nice", "great", "tell me more", "wow", "good", "useful"]),
        "payment_done":    any(w in msg for w in ["paid", "payment done", "transferred", "sent money", "done the payment"]),
    }

    # Score delta
    points = 0
    if signals.get("asks_price"):     points += 10
    if signals.get("asks_demo"):      points += 15
    if signals.get("asks_trial"):     points += 15
    if signals.get("asks_setup"):     points += 10
    if signals.get("asks_how_start"): points += 20
    if signals.get("ready_to_buy"):   points += 30
    if signals.get("positive"):       points += 5
    if signals.get("payment_done"):   points += 50

    new_score = min(100, state.get("interest_score", 0) + points)

    # Track objections
    existing_obj = list(state.get("objections", []) or [])
    if signals.get("price_objection") and "price" not in existing_obj:
        existing_obj.append("price")
    if signals.get("skeptical") and "skeptical" not in existing_obj:
        existing_obj.append("skeptical")

    # Extract qualification data from their answers
    qual_updates = _extract_qual_data(state.get("user_message", ""), state)

    return {
        "signals": signals,
        "score_delta": points,
        "interest_score": new_score,
        "objections": existing_obj,
        **qual_updates,
    }


def _extract_qual_data(message: str, state: dict) -> Dict[str, Any]:
    """Simple pattern extraction to capture qualification answers."""
    updates = {}
    msg = message.lower()

    # Inquiry volume hints
    for pattern in [r"(\d+)\s*(messages?|inquiries|patients|msgs)", r"(many|few|lots|50|100|200|20|30|40|10|15|25)"]:
        m = re.search(pattern, msg)
        if m and not state.get("inquiry_volume"):
            updates["inquiry_volume"] = m.group(0)
            break

    # Who handles
    if not state.get("who_handles"):
        for phrase in ["i do", "myself", "staff", "receptionist", "assistant", "team", "nurse"]:
            if phrase in msg:
                updates["who_handles"] = phrase
                break

    # Booking process
    if not state.get("booking_process"):
        for phrase in ["phone", "whatsapp", "walk in", "walk-in", "app", "website", "google", "online"]:
            if phrase in msg:
                updates["booking_process"] = phrase
                break

    return updates


# ═══════════════════════════════════════════════════════════════════════════════
# NODE 2.5: ORCHESTRATOR — The Super Brain
# ═══════════════════════════════════════════════════════════════════════════════

def node_orchestrate(state: dict) -> dict:
    """
    THE SUPER BRAIN.

    Runs a fast structured LLM call to deeply analyze the lead before the
    response agent speaks. Outputs a complete tactical brief that the
    response agent executes — it no longer needs to figure anything out itself.

    Outputs:
        orchestrator_brief: dict with all analysis results
    """
    if state.get("should_stop"):
        return {}

    # ── Build a comprehensive profile of everything we know ──────────────────
    msg        = state.get("user_message", "")
    stage      = state.get("stage", "QUALIFY")
    signals    = state.get("signals", {})
    lead_data  = state.get("lead_data", {})
    history    = state.get("messages", [])

    # Resolve all identity fields
    clinic         = state.get("clinic_name") or lead_data.get("clinic_name") or ""
    owner          = state.get("owner_name")  or lead_data.get("owner_name")  or ""
    city           = state.get("city")         or lead_data.get("city")        or ""
    category       = state.get("category")     or lead_data.get("category")    or ""
    weakness       = state.get("weakness_summary") or lead_data.get("weakness_summary") or ""
    google_rating  = state.get("google_rating") or lead_data.get("google_rating") or ""
    review_count   = state.get("review_count")  or lead_data.get("review_count")  or ""
    website        = state.get("website")        or lead_data.get("website")        or ""
    missing_phone  = state.get("missing_phone",  0)
    missing_hours  = state.get("missing_hours",  0)
    slow_response  = state.get("slow_response",  0)
    interest_score = state.get("interest_score", 0)
    objections     = state.get("objections", [])
    inquiry_vol    = state.get("inquiry_volume", "")
    who_handles    = state.get("who_handles", "")
    booking_proc   = state.get("booking_process", "")

    # Summarize conversation history briefly
    history_summary = ""
    if history:
        last_3 = history[-6:]  # Last 3 exchanges
        history_summary = "\n".join([
            f"{'Lead' if m.get('role') == 'user' else 'Us'}: {m.get('content', '')[:120]}"
            for m in last_3
        ])

    # ── Build the intel dossier for the orchestrator ──────────────────────────
    dossier_parts = []
    if clinic:   dossier_parts.append(f"Business: {clinic}{f', {city}' if city else ''}")
    if owner:    dossier_parts.append(f"Owner/Contact: {owner}")
    if category: dossier_parts.append(f"Type: {category}")
    if weakness: dossier_parts.append(f"Known weakness: {weakness}")
    if google_rating:
        dossier_parts.append(f"Google rating: {google_rating}/5 ({review_count or '?'} reviews)")
    if website:        dossier_parts.append(f"Website: {website}")
    if missing_phone:  dossier_parts.append("SIGNAL: No phone number visible online")
    if missing_hours:  dossier_parts.append("SIGNAL: Business hours not listed")
    if slow_response:  dossier_parts.append("SIGNAL: Detected slow/no WhatsApp reply time")
    if inquiry_vol:    dossier_parts.append(f"Gets ~{inquiry_vol} inquiries")
    if who_handles:    dossier_parts.append(f"Currently handled by: {who_handles}")
    if booking_proc:   dossier_parts.append(f"Booking method: {booking_proc}")
    if objections:     dossier_parts.append(f"Past objections: {', '.join(objections)}")
    dossier_parts.append(f"Interest score: {interest_score}/100")
    dossier_parts.append(f"Current stage: {stage}")

    dossier = "\n".join(dossier_parts) if dossier_parts else "No pre-existing intel available."

    orchestrator_prompt = f"""You are the Intelligence Director for an elite B2B sales system.
Your job: analyze the incoming message and the lead's full profile, then produce a tactical brief for the sales agent.

=== LEAD DOSSIER ===
{dossier}

=== CONVERSATION HISTORY (last 3 exchanges) ===
{history_summary or 'No prior messages.'}

=== INCOMING MESSAGE ===
"{msg}"

=== YOUR TASK ===
Analyze everything and respond with ONLY a valid JSON object. No markdown, no explanation.

Required fields:
{{
  "intent": "one of: greeting | qualifying_answer | asking_price | asking_demo | asking_setup | objection_price | objection_skeptical | objection_busy | positive_interest | ready_to_buy | wants_human | unrelated | not_interested",
  "sentiment": "one of: very_positive | positive | neutral | negative | hostile",
  "buying_signal_strength": 0-100,
  "key_pain_point": "The single most powerful pain to address right now given what we know about them. Be specific to their situation. E.g. 'They manually reply to 20+ messages/day and are losing bookings to faster competitors'",
  "personalization_hook": "One specific thing from their profile to reference naturally. E.g. 'Their Google listing has no phone number' or 'They have 4.2 stars but only 23 reviews — patients like them but can't find them'. Leave blank string if no intel available.",
  "response_strategy": "Precise instructions for the response agent in 1-2 sentences. What to say, what NOT to say, what question to ask next, what tone to use.",
  "recommended_stage": "one of: QUALIFY | PROBLEM | SOLUTION | OFFER | CLOSE | HUMAN | LOST",
  "urgency": "one of: low | medium | high"
}}"""

    brief = {}
    try:
        client = _get_client()
        resp = client.chat.completions.create(
            model="gpt-4o-mini",   # Fast + cheap for analysis
            messages=[{"role": "user", "content": orchestrator_prompt}],
            temperature=0.1,       # Deterministic analysis
            max_tokens=400,
            response_format={"type": "json_object"},
        )
        import json
        raw = resp.choices[0].message.content.strip()
        brief = json.loads(raw)
        print(f"[ORCHESTRATOR] intent={brief.get('intent')} signal={brief.get('buying_signal_strength')} stage={brief.get('recommended_stage')}")
    except Exception as e:
        import traceback
        print(f"[ORCHESTRATOR] Failed (non-fatal): {e}")
        print(traceback.format_exc())
        # Safe defaults — show must go on
        brief = {
            "intent": "unknown",
            "sentiment": "neutral",
            "buying_signal_strength": interest_score,
            "key_pain_point": weakness or "manual WhatsApp replies costing them bookings",
            "personalization_hook": "",
            "response_strategy": f"Continue the conversation naturally for stage {stage}.",
            "recommended_stage": stage,
            "urgency": "medium",
        }

    # Update recommended stage if different from current
    new_stage = brief.get("recommended_stage", stage)
    # Only allow forward or lateral moves — never go backwards more than one stage
    stage_order = ["QUALIFY", "PROBLEM", "SOLUTION", "OFFER", "CLOSE", "WON", "LOST", "HUMAN"]
    current_idx = stage_order.index(stage) if stage in stage_order else 0
    new_idx     = stage_order.index(new_stage) if new_stage in stage_order else 0
    # Allow forward moves and any terminal states
    if new_idx >= current_idx or new_stage in ("LOST", "HUMAN"):
        resolved_stage = new_stage
    else:
        resolved_stage = stage

    return {
        "orchestrator_brief": brief,
        "stage": resolved_stage,
        # Boost score from orchestrator signal
        "interest_score": min(100, interest_score + max(0, brief.get("buying_signal_strength", 0) - interest_score) // 3),
    }



def node_draft_response(state: dict) -> dict:
    """
    Call the LLM using the stage-specific prompt + orchestrator brief + conversation history.
    The Orchestrator has already done all the thinking. This node just EXECUTES.
    Falls back to a pre-written message if the LLM is unavailable.
    """
    if state.get("should_stop"):
        return {"reply_text": "", "raw_llm_output": ""}

    stage     = state.get("stage", "QUALIFY")
    channel   = state.get("channel", "whatsapp")
    lead_data = state.get("lead_data", {})
    brief     = state.get("orchestrator_brief", {})

    # ── Build the base system prompt (stage + lead context) ──────────────────
    system_prompt = build_system_prompt(stage, lead_data, state, channel)

    # ── Inject the Orchestrator brief as a high-priority addendum ────────────
    if brief:
        intent   = brief.get("intent", "")
        pain     = brief.get("key_pain_point", "")
        hook     = brief.get("personalization_hook", "")
        strategy = brief.get("response_strategy", "")
        urgency  = brief.get("urgency", "medium")
        sentiment = brief.get("sentiment", "neutral")

        brief_block = f"""
═══════════════════════════════════════════
INTELLIGENCE BRIEF FROM ORCHESTRATOR
(read this carefully — it overrides any generic instincts)
═══════════════════════════════════════════
Lead intent right now: {intent}
Their emotional state: {sentiment}
Urgency level: {urgency}

Most powerful pain to address: {pain}

Personalization hook to use naturally (use 1 only, don't force it): {hook or 'None available'}

EXACT STRATEGY FOR YOUR REPLY:
{strategy}
═══════════════════════════════════════════
REMEMBER: No dashes, no bullets. Flowing sentences. Use [SPLIT] for multiple bubbles.
""".strip()

        system_prompt = system_prompt + "\n\n" + brief_block

    messages_payload = (
        [{"role": "system", "content": system_prompt}]
        + (state.get("messages") or [])
        + [{"role": "user", "content": state.get("user_message", "")}]
    )

    reply_text = None
    try:
        client = _get_client()
        resp = client.chat.completions.create(
            model=_model(),
            messages=messages_payload,
            temperature=0.7,
            max_tokens=500,
        )
        reply_text = resp.choices[0].message.content.strip()
    except Exception as e:
        import traceback
        print(f"OpenAI Draft Failed: {e}")
        print(traceback.format_exc())
        reply_text = get_fallback(stage)

    return {"raw_llm_output": reply_text}


# ═══════════════════════════════════════════════════════════════════════════════
# NODE 4: PROCESS TAGS & TRANSITION STATE
# ═══════════════════════════════════════════════════════════════════════════════

def node_process_tags(state: dict) -> dict:
    """
    Parse control tags from the LLM output, determine the next stage,
    and log any special events (demo booked, payment, etc.).
    """
    if state.get("should_stop"):
        return {}

    raw = state.get("raw_llm_output", "")
    phone = state["phone"]

    # Extract tags
    llm_stage_tag    = _extract_state_tag(raw)
    llm_interest     = _extract_interest_delta(raw)
    has_escalate     = "[ESCALATE]" in raw
    has_demo_booked  = "[DEMO_BOOKED]" in raw
    has_payment_link = "[PAYMENT_LINK]" in raw
    has_trial_link   = "[TRIAL_LINK]" in raw

    # Update score
    new_score = min(100, state.get("interest_score", 0) + llm_interest)

    # Determine next stage
    signals = state.get("signals", {})
    current = state.get("stage", "QUALIFY")
    next_stage = _next_stage(current, signals, state, llm_stage_tag)

    updates = {
        "interest_score": new_score,
        "stage": next_stage,
        "demo_booked": False,
        "trial_activated": False,
        "payment_sent": False,
        "payment_completed": False,
        "human_escalation": False,
    }

    # Handle special flags
    if has_escalate or signals.get("wants_human"):
        updates["human_escalation"] = True
        updates["stage"] = "HUMAN"
        db.log_event(phone, "HUMAN_ESCALATION", state.get("user_message", "")[:80])
    if has_demo_booked:
        updates["demo_booked"] = True
        updates["stage"] = "WON"
        db.log_event(phone, "DEMO_BOOKED", "")
    if has_trial_link or signals.get("asks_trial"):
        updates["trial_activated"] = True
        updates["stage"] = "WON"
        db.log_event(phone, "TRIAL_ACTIVATED", "")
    if has_payment_link:
        updates["payment_sent"] = True
        db.log_event(phone, "PAYMENT_LINK_SENT", "")
    if signals.get("payment_done"):
        updates["payment_completed"] = True
        updates["stage"] = "WON"
        db.log_event(phone, "PAYMENT_COMPLETED", "")

    # Clean the response (strip internal tags before sending)
    clean_reply = _clean_response(raw)
    updates["reply_text"] = clean_reply

    return updates


# ═══════════════════════════════════════════════════════════════════════════════
# NODE 5: PERSIST (Save to DB)
# ═══════════════════════════════════════════════════════════════════════════════

def node_persist(state: dict) -> dict:
    """
    Save everything to the database: user message, assistant reply, and updated state.
    """
    phone = state["phone"]
    channel = state.get("channel", "whatsapp")
    user_msg = state.get("user_message", "")
    reply = state.get("reply_text", "")

    # Log first reply event
    if not state.get("messages"):
        db.log_event(phone, "FIRST_REPLY", user_msg[:100])

    # Save messages
    db.save_message(phone, "user", user_msg, channel)
    if reply:
        db.save_message(phone, "assistant", reply, channel)

    # Build state updates dict for the DB
    db_updates = {
        "stage": state.get("stage", "QUALIFY"),
        "interest_score": state.get("interest_score", 0),
        "objections": state.get("objections", []),
    }
    # Conditionally add qualification data
    for key in ["inquiry_volume", "who_handles", "booking_process", "contact_name", "business_name"]:
        if state.get(key):
            db_updates[key] = state[key]

    # Add conversion flags
    if state.get("human_escalation"):
        db_updates["human_escalation"] = 1
    if state.get("demo_booked"):
        db_updates["demo_booked"] = 1
    if state.get("trial_activated"):
        db_updates["trial_activated"] = 1
    if state.get("payment_sent"):
        db_updates["payment_sent"] = 1
    if state.get("payment_completed"):
        db_updates["payment_completed"] = 1

    db.save_state(phone, db_updates)

    return {}


# ═══════════════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def _next_stage(current: str, signals: Dict, state: Dict, llm_tag: Optional[str]) -> str:
    """Determine next stage from LLM tag + signals + current stage."""
    if llm_tag and llm_tag in ("QUALIFY", "PROBLEM", "SOLUTION", "OFFER", "CLOSE", "WON", "LOST", "HUMAN", "NURTURE"):
        return llm_tag

    score = state.get("interest_score", 0)
    if signals.get("not_interested"):
        return "LOST"
    if signals.get("wants_human"):
        return "HUMAN"
    if signals.get("payment_done"):
        return "WON"
    if signals.get("ready_to_buy") and current in ("OFFER", "CLOSE"):
        return "CLOSE"
    if signals.get("asks_price") and current not in ("CLOSE", "WON", "LOST"):
        return "CLOSE"
    if (signals.get("asks_demo") or signals.get("asks_trial")) and current not in ("CLOSE", "WON", "LOST"):
        return "CLOSE"
    if current == "QUALIFY" and score >= 5 and (
        state.get("inquiry_volume") or state.get("who_handles") or state.get("booking_process")
    ):
        return "PROBLEM"
    if current == "PROBLEM" and score >= 10:
        return "SOLUTION"
    if current == "SOLUTION" and score >= 20:
        return "OFFER"

    return current


def _extract_state_tag(text: str) -> Optional[str]:
    m = re.search(r"\[STATE:(\w+)\]", text)
    return m.group(1) if m else None


def _extract_interest_delta(text: str) -> int:
    m = re.search(r"\[INTEREST:\+(\d+)\]", text)
    return int(m.group(1)) if m else 0


def _clean_response(text: str) -> str:
    """Remove internal control tags from the response before sending."""
    return re.sub(
        r"\[(STATE|INTEREST|ESCALATE|DEMO_BOOKED|PAYMENT_LINK|TRIAL_LINK):[^\]]*\]|\[(ESCALATE|DEMO_BOOKED|PAYMENT_LINK|TRIAL_LINK)\]",
        "", text
    ).strip()
