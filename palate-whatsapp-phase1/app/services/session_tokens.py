from __future__ import annotations

import re
import secrets
import string
from urllib.parse import quote_plus

from app.core.security import sha256_text
from app.services.copy_utils import short_restaurant_name

TOKEN_PATTERN = re.compile(r"\bPALATE_[A-Z0-9]{8}\b")


def generate_session_token() -> str:
    alphabet = string.ascii_uppercase + string.digits
    suffix = "".join(secrets.choice(alphabet) for _ in range(8))
    return f"PALATE_{suffix}"


def hash_session_token(token: str, pepper: str) -> str:
    return sha256_text(f"{token}:{pepper}")


def token_hint(token: str) -> str:
    return token[-4:]


def extract_session_token(text: str | None) -> str | None:
    if not text:
        return None
    match = TOKEN_PATTERN.search(text.upper())
    return match.group(0) if match else None


def build_prefilled_message(token: str, restaurant_name: str, reference: str) -> str:
    restaurant = short_restaurant_name(restaurant_name)
    return f"Start my Palate session and show me {restaurant}'s menu\nToken: {token}"


def build_wa_link(whatsapp_number: str, message: str) -> str:
    destination = whatsapp_number.lstrip("+")
    return f"https://wa.me/{destination}?text={quote_plus(message)}"
