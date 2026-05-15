from __future__ import annotations

import hashlib
import hmac
import re
from typing import Optional

from twilio.request_validator import RequestValidator


def constant_time_compare(left: str, right: str) -> bool:
    return hmac.compare_digest(left.encode("utf-8"), right.encode("utf-8"))


def normalize_phone(phone: Optional[str]) -> Optional[str]:
    if phone is None:
        return None
    cleaned = re.sub(r"[^\d+]", "", phone.strip())
    if not cleaned:
        return None
    if cleaned.startswith("00"):
        cleaned = f"+{cleaned[2:]}"
    elif not cleaned.startswith("+"):
        cleaned = f"+{cleaned}"
    return cleaned


def build_hmac_sha256(secret: str, payload: bytes) -> str:
    return hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()


def verify_meta_signature(signature_header: str | None, payload: bytes, app_secret: str) -> bool:
    if not signature_header or not signature_header.startswith("sha256="):
        return False
    expected = build_hmac_sha256(app_secret, payload)
    provided = signature_header.split("=", 1)[1]
    return hmac.compare_digest(expected, provided)


def verify_razorpay_signature(signature_header: str | None, payload: bytes, secret: str) -> bool:
    if not signature_header:
        return False
    expected = build_hmac_sha256(secret, payload)
    return hmac.compare_digest(expected, signature_header)


def verify_twilio_signature(
    signature_header: str | None,
    request_url: str,
    form_params: dict[str, str],
    auth_token: str,
) -> bool:
    if not signature_header:
        return False
    validator = RequestValidator(auth_token)
    return bool(validator.validate(request_url, form_params, signature_header))


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
