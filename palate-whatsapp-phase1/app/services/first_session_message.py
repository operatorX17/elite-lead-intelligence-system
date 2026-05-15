from __future__ import annotations

from app.db.models import WhatsAppSession
from app.services.copy_utils import display_customer_name, short_restaurant_name


FIRST_SESSION_STAGES = {"landing", "menu", "unknown"}


def _menu_url(session: WhatsAppSession) -> str | None:
    metadata = session.metadata_json or {}
    original = metadata.get("original_resume_url")
    if isinstance(original, str) and original:
        return original
    return session.resume_url


def _restaurant(session: WhatsAppSession) -> str:
    return short_restaurant_name(session.restaurant_name)


def should_send_first_session_welcome(session: WhatsAppSession) -> bool:
    metadata = session.metadata_json or {}
    if metadata.get("disable_first_session_welcome") is True:
        return False
    return (session.entry_point or "unknown") in FIRST_SESSION_STAGES


def compose_first_session_welcome(session: WhatsAppSession) -> str:
    restaurant = _restaurant(session)
    menu_url = _menu_url(session)
    customer_name = display_customer_name(session.provided_name)
    parts = [
        f"Hi {customer_name}, welcome to Palate.",
        f"Here is {restaurant}'s menu. Tap any dish to leave a review:",
    ]
    if menu_url:
        parts.append(menu_url)
    return "\n".join(parts)


def compose_first_session_followup() -> str:
    return "\n".join(
        [
            "One thing that makes us different: you rate the dish, not the restaurant.",
            "Because one place can have a brilliant dal and a forgettable paneer, and you deserve to know which is which.",
        ]
    )
