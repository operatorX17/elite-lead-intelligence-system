"""Shared clinic sales playbook helpers for conversation and outreach agents."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple


SALES_STAGES = {
    "NEW",
    "ENGAGED",
    "QUALIFIED",
    "PAIN_FOUND",
    "PROOF_SHARED",
    "OBJECTION_ACTIVE",
    "DEMO_PUSHED",
    "PAYMENT_PUSHED",
    "HUMAN_HANDOFF",
    "FOLLOWUP_PENDING",
    "CLOSED_WON",
    "CLOSED_LOST",
}

SUPPORTED_CHANNELS = {
    "email",
    "linkedin",
    "sms",
    "whatsapp",
    "instagram",
    "website_chat",
    "dm",
    "form",
}

OPT_OUT_PATTERNS = (
    r"\bstop\b",
    r"\bunsubscribe\b",
    r"\bremove me\b",
    r"\bdo not contact\b",
    r"\bdon't contact\b",
    r"\bnot interested\b",
)

HUMAN_HANDOFF_PATTERNS = (
    r"\bhuman\b",
    r"\bfounder\b",
    r"\bowner\b",
    r"\bcall me\b",
    r"\blive demo\b",
    r"\blive walkthrough\b",
    r"\bconnect me\b",
    r"\btalk to my manager\b",
)

OBJECTION_PATTERNS: Dict[str, Tuple[str, ...]] = {
    "price": (r"\bprice\b", r"\bcost\b", r"\bexpensive\b", r"\btoo much\b", r"\bbudget\b"),
    "timing": (r"\bnot now\b", r"\blater\b", r"\bnext month\b", r"\bafter one month\b", r"\bbusy\b"),
    "integration": (r"\bintegrat", r"\bcrm\b", r"\bcurrent setup\b", r"\bexisting system\b"),
    "human_preference": (r"\bhuman\b", r"\breceptionist\b", r"\bstaff\b", r"\bpatients prefer humans\b"),
    "trust": (r"\bwho else\b", r"\bproof\b", r"\bcase stud", r"\bhow is this different\b"),
    "spam": (r"\bspam\b", r"\bspammy\b", r"\btoo many messages\b"),
    "safety": (r"\bsafe\b", r"\bcompliance\b", r"\bhealthcare\b", r"\bdata\b"),
    "roi": (r"\bmore bookings\b", r"\bactual patients\b", r"\bwill this work\b"),
    "brochure": (r"\bsend details\b", r"\bbrochure\b", r"\bsend info\b"),
    "manager": (r"\bmanager\b", r"\bdecision maker\b", r"\bdoctor\b", r"\bowner\b"),
    "payment": (r"\bpayment\b", r"\bpay\b", r"\bpilot\b"),
}

PAIN_PATTERNS: Dict[str, Tuple[str, ...]] = {
    "missed_follow_up": (r"\bmissed\b", r"\bdrop off\b", r"\bdropped\b", r"\bno follow[- ]?up\b"),
    "slow_response": (r"\bslow\b", r"\blate\b", r"\bdelay\b", r"\bnot replied\b", r"\bresponse\b"),
    "whatsapp_gap": (r"\bwhatsapp\b", r"\bchat\b"),
    "instagram_gap": (r"\binstagram\b", r"\bdm\b"),
    "booking_gap": (r"\bbooking\b", r"\bappointment\b", r"\bconsultation\b"),
    "no_show": (r"\bno[- ]?show\b", r"\bdidn'?t come\b", r"\bdrop after booking\b"),
    "staff_dependency": (r"\bstaff\b", r"\breception\b", r"\bfront desk\b", r"\bmanual\b"),
}

CHANNEL_HINT_PATTERNS: Dict[str, Tuple[str, ...]] = {
    "whatsapp": (r"\bwhatsapp\b",),
    "instagram": (r"\binstagram\b", r"\bdm\b"),
    "email": (r"\bemail\b", r"\bmail\b"),
    "website_chat": (r"\bwebsite\b", r"\bsite\b", r"\bchat\b"),
    "phone": (r"\bcall\b", r"\bphone\b"),
    "google": (r"\bgoogle\b", r"\bmaps\b"),
    "ads": (r"\bads\b", r"\bmeta\b", r"\bfacebook ads\b", r"\binstagram ads\b"),
    "referrals": (r"\breferral\b", r"\bword of mouth\b"),
}

ROLE_PATTERNS: Dict[str, Tuple[str, ...]] = {
    "founder": (r"\bfounder\b", r"\bowner\b"),
    "doctor": (r"\bdoctor\b", r"\bdr\b", r"\bdermatologist\b", r"\bdentist\b"),
    "manager": (r"\bmanager\b", r"\badmin\b"),
    "reception": (r"\breception\b", r"\bfront desk\b", r"\bcoordinator\b"),
}

SELF_OWNERSHIP_PATTERNS: Tuple[str, ...] = (
    r"\bi handle it(?: myself)?\b",
    r"\bi manage it(?: myself)?\b",
    r"\bi oversee it(?: myself)?\b",
    r"\bjust me\b",
    r"\bit'?s me\b",
    r"\bi do\b",
)


def normalize_channel(value: Optional[str]) -> str:
    channel = str(value or "").strip().lower() or "email"
    if channel in {"ig", "instagram_dm", "insta"}:
        channel = "instagram"
    if channel in {"chat", "website", "webchat"}:
        channel = "website_chat"
    if channel not in SUPPORTED_CHANNELS:
        return "email"
    return channel


def _detect_matches(message: str, pattern_map: Dict[str, Tuple[str, ...]]) -> List[str]:
    lowered = str(message or "").lower()
    matches: List[str] = []
    for label, patterns in pattern_map.items():
        if any(re.search(pattern, lowered) for pattern in patterns):
            matches.append(label)
    return matches


def detect_opt_out(message: str) -> bool:
    lowered = str(message or "").lower()
    return any(re.search(pattern, lowered) for pattern in OPT_OUT_PATTERNS)


def detect_human_handoff(message: str) -> bool:
    lowered = str(message or "").lower()
    return any(re.search(pattern, lowered) for pattern in HUMAN_HANDOFF_PATTERNS)


def infer_role_from_message(message: str) -> Optional[str]:
    lowered = str(message or "").lower()
    for role, patterns in ROLE_PATTERNS.items():
        if any(re.search(pattern, lowered) for pattern in patterns):
            return role
    return None


def infer_next_step_request(message: str) -> Optional[str]:
    lowered = str(message or "").lower()
    if any(token in lowered for token in ("call", "speak", "talk", "demo", "walkthrough")):
        return "call"
    if any(token in lowered for token in ("details", "brochure", "send", "info", "explain")):
        return "details"
    if any(
        token in lowered
        for token in (
            "what would you change first",
            "what would you fix first",
            "what should i change first",
            "what should i fix first",
            "change first",
            "fix first",
        )
    ):
        return "details"
    if any(token in lowered for token in ("price", "pricing", "cost")):
        return "pricing"
    if any(token in lowered for token in ("later", "next month", "after one month")):
        return "follow_up_later"
    if any(token in lowered for token in ("payment", "pay", "pilot")):
        return "payment"
    return None


def infer_sales_stage(entities: Dict[str, Any]) -> str:
    current = str(entities.get("stage") or "").upper()
    objection_categories = {
        str(category or "").strip().lower()
        for category in (entities.get("objection_categories") or [])
        if str(category or "").strip()
    }
    substantive_objections = objection_categories - {"timing", "brochure", "manager"}
    if current in {"CLOSED_WON", "CLOSED_LOST"}:
        return current
    if entities.get("opt_out"):
        return "CLOSED_LOST"
    if entities.get("handoff_requested") or entities.get("payment_interest"):
        return "HUMAN_HANDOFF"
    if entities.get("requested_next_step") == "payment":
        return "PAYMENT_PUSHED"
    if entities.get("requested_next_step") == "call":
        return "DEMO_PUSHED"
    if substantive_objections:
        return "OBJECTION_ACTIVE"
    if entities.get("pain_confirmed") and entities.get("requested_next_step") == "details":
        return "PROOF_SHARED"
    if entities.get("pain_confirmed") and entities.get("decision_maker_confirmed"):
        return "QUALIFIED"
    if entities.get("pain_confirmed"):
        return "PAIN_FOUND"
    if entities.get("last_intent"):
        return "ENGAGED"
    return "NEW"


def classify_sales_signals(message: str) -> Dict[str, Any]:
    lead_channels = _detect_matches(message, CHANNEL_HINT_PATTERNS)
    objection_categories = _detect_matches(message, OBJECTION_PATTERNS)
    pain_points = _detect_matches(message, PAIN_PATTERNS)
    role = infer_role_from_message(message)
    current_reply_owner = None
    decision_maker_confirmed = False
    decision_maker_role = None
    lowered = str(message or "").lower()
    if any(re.search(pattern, lowered) for pattern in SELF_OWNERSHIP_PATTERNS):
        current_reply_owner = "owner"
        decision_maker_confirmed = True
        decision_maker_role = role or "owner"
        role = role or "owner"
    requested_next_step = infer_next_step_request(message)
    payment_interest = "payment" in objection_categories or requested_next_step == "payment"
    handoff_requested = detect_human_handoff(message)
    return {
        "lead_channels": lead_channels,
        "objection_categories": objection_categories,
        "pain_points": pain_points,
        "role": role,
        "current_reply_owner": current_reply_owner,
        "decision_maker_confirmed": decision_maker_confirmed,
        "decision_maker_role": decision_maker_role,
        "requested_next_step": requested_next_step,
        "payment_interest": payment_interest,
        "handoff_requested": handoff_requested,
        "opt_out": detect_opt_out(message),
    }


def should_escalate_to_human(entities: Dict[str, Any]) -> Tuple[bool, List[str]]:
    reasons: List[str] = []
    if entities.get("handoff_requested"):
        reasons.append("Requested a human or founder")
    if entities.get("payment_interest"):
        reasons.append("Payment or pilot discussion is active")
    if "safety" in (entities.get("objection_categories") or []):
        reasons.append("Compliance or safety concern needs precise human handling")
    if "integration" in (entities.get("objection_categories") or []):
        reasons.append("Custom integration concern needs implementation confirmation")
    if entities.get("decision_maker_confirmed") and entities.get("pain_confirmed") and entities.get("requested_next_step") == "call":
        reasons.append("Qualified lead is ready for a live walkthrough")
    if (entities.get("confidence") or 0) < 0.35 and entities.get("last_intent"):
        reasons.append("Low confidence in conversation interpretation")
    return bool(reasons), reasons


def build_sales_system_prompt(
    *,
    lead: Dict[str, Any],
    entities: Dict[str, Any],
    analysis_bundle: Optional[Dict[str, Any]],
    missing_info: List[str],
    channel: str,
) -> str:
    analysis_bundle = analysis_bundle or {}
    facts = analysis_bundle.get("facts") or {}
    guidance = analysis_bundle.get("guidance") or {}
    agent_context = analysis_bundle.get("agent_context") or {}
    stage = infer_sales_stage(entities)
    trust_markers = ", ".join(agent_context.get("trust_markers") or [])
    known_pains = ", ".join(agent_context.get("known_pain_points") or [])
    decision_maker = agent_context.get("decision_maker_name") or facts.get("decision_maker_name") or "unknown"
    recommended_offer = agent_context.get("recommended_offer") or "lead conversion improvement"
    top_issue = guidance.get("top_issue") or facts.get("top_issue") or "conversion leak"
    next_action = guidance.get("next_best_action") or facts.get("next_best_action") or "continue diagnosing calmly"

    stage_guidance = {
        "NEW": "Acknowledge, stay calm, and ask one short contextual question only if needed.",
        "ENGAGED": "Answer what they asked, keep it practical, and ask one low-friction follow-up only if it helps.",
        "PAIN_FOUND": "Stay grounded in the problem they already mentioned. Give one useful observation before asking for more.",
        "QUALIFIED": "Be helpful and specific. Move toward a next step only if it feels earned from the conversation.",
        "PROOF_SHARED": "Use one concrete observation and only one light next step.",
        "OBJECTION_ACTIVE": "Handle the concern directly and practically. Do not slip back into generic discovery questions.",
        "DEMO_PUSHED": "Offer a short time-boxed call with forced-choice scheduling.",
        "PAYMENT_PUSHED": "Keep it precise and handoff-ready. Do not invent links or promises.",
        "HUMAN_HANDOFF": "Do not over-handle. Prepare a clean bridge to a human closer.",
        "FOLLOWUP_PENDING": "Use a short contextual follow-up, not a long explanation.",
    }.get(stage, "Keep moving the conversation one useful step forward without pressure.")

    channel_guidance = {
        "whatsapp": "Reply in 1-3 short chat bubbles worth of text. Very natural. No markdown.",
        "instagram": "Keep it tight and casual-professional. Shorter than email. No markdown.",
        "website_chat": "Qualify quickly and move toward booking or a callback. No markdown.",
        "linkedin": "Polished and concise. One smart observation, one next step.",
        "sms": "Ultra concise and direct. One thought, one next step.",
        "email": "Slightly more structured, but still human and short.",
    }.get(channel, "Keep it concise, human, and easy to read.")

    return f"""You are a human-sounding clinic sales closer for {lead.get('business_name', 'this clinic')}.

Voice:
- Calm, respectful, commercially mature, Indian-market aware
- Never robotic, never cheesy, never overhyped
- Never say you are an AI
- Never use bullet formatting in the live reply
- Keep replies short unless the lead explicitly asks for detail
- Avoid internal jargon like leak, leakage, handoff, lane, funnel, or conversion gap unless the contact already speaks that way
- Do not sound like an auditor, consultant deck, CRM note, or internal sales playbook

Rules:
- Do not pitch too early
- Do not explain tech unless asked
- Do not invent case studies, metrics, or guarantees
- Do not call a branch phone a founder-direct contact unless that is verified
- If the lead wants to stop, comply immediately and keep the response minimal
- Use only one meaningful next step per reply
- If they ask a direct question, answer it first in plain language, then ask at most one short follow-up
- Prefer concrete language over frameworks or labels

Internal stage: {stage}
Stage guidance: {stage_guidance}
Channel guidance: {channel_guidance}

Missing information: {", ".join(missing_info) if missing_info else "No critical gaps"}

Grounded business context:
- Clinic type: {lead.get('category') or facts.get('services') or 'clinic'}
- Geography: {lead.get('location') or 'unknown'}
- Trust markers: {trust_markers or 'limited'}
- Known pain points: {known_pains or 'not yet confirmed'}
- Top issue: {top_issue}
- Recommended offer (internal only): {recommended_offer}
- Next best action (internal only): {next_action}
- Likely decision maker: {decision_maker}

Your objective hierarchy:
1. Understand what they actually need right now
2. Answer clearly and naturally
3. Qualify only when it genuinely helps
4. Build trust with specifics from the real context
5. Move to one next step only when it is earned

Do not rush to a demo just because you can. Earn the next step."""


def build_sales_fallback_response(
    entities: Dict[str, Any],
    analysis_bundle: Optional[Dict[str, Any]],
) -> str:
    guidance = (analysis_bundle or {}).get("guidance") or {}
    top_issue = guidance.get("top_issue") or "the first reply window"

    if entities.get("opt_out"):
        return "Understood. I'll close the loop here and won't continue the follow-up."
    if entities.get("requested_next_step") == "details":
        return (
            f"First thing I'd tighten is {top_issue}. "
            "If you want, I can break down the exact change I'd make first."
        )
    if entities.get("requested_next_step") == "call":
        return "Makes sense. A quick 10-minute look will be cleaner than a long message. Would this evening or tomorrow afternoon be easier?"
    if not entities.get("pain_confirmed"):
        return (
            f"I was asking because small delays around {top_issue} can quietly cost bookings over time. "
            "Have you noticed that happening on your side?"
        )
    if entities.get("objection_categories"):
        return "Fair point. I'm not suggesting more chaos, just a cleaner way to keep warm enquiries moving. Would it help if I kept it to the exact point I'd tighten first?"
    if not entities.get("decision_maker_confirmed"):
        return "Makes sense. Is that mostly on you right now, or does someone else help with replies?"
    return (
        f"I'd start with {top_issue}. "
        "That is usually the first thing to tighten before touching anything else."
    )
