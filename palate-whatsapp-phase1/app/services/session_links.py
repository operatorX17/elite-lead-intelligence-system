from __future__ import annotations

from datetime import timedelta

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.exceptions import AppError
from app.core.security import normalize_phone
from app.db.base import utcnow
from app.db.models import Customer, Order, WhatsAppSession
from app.schemas import SessionLinkResponse
from app.services.session_tokens import (
    build_prefilled_message,
    build_wa_link,
    generate_session_token,
    hash_session_token,
    token_hint,
)


def _resolve_destination_number(settings: Settings) -> str:
    destination_number = settings.session_link_whatsapp_number
    if not destination_number:
        if settings.whatsapp_provider == "twilio":
            raise AppError(503, "twilio_whatsapp_from_missing", "TWILIO_WHATSAPP_FROM is not configured")
        raise AppError(503, "whatsapp_number_missing", "PALATE_WHATSAPP_NUMBER is not configured")
    return destination_number


def create_session_link_for_context(
    db: Session,
    settings: Settings,
    *,
    order: Order | None,
    customer: Customer | None,
    restaurant_id: str,
    restaurant_name: str,
    customer_name: str | None,
    provided_phone: str | None,
    entry_point: str,
    intent: str,
    resume_url: str | None,
    metadata: dict | None = None,
    expires_in_minutes: int,
) -> SessionLinkResponse:
    if settings.session_token_pepper is None:
        raise AppError(503, "session_pepper_missing", "SESSION_TOKEN_PEPPER is not configured")

    destination_number = _resolve_destination_number(settings)
    normalized_provided_phone = normalize_phone(provided_phone)

    if customer is None and (customer_name or normalized_provided_phone):
        customer = Customer(
            display_name=customer_name,
            phone_e164=normalized_provided_phone,
            onboarding_status="pending_verification",
            onboarding_source=entry_point,
        )
        db.add(customer)
        db.flush()
    elif customer is not None:
        customer.display_name = customer_name or customer.display_name
        customer.phone_e164 = normalized_provided_phone or customer.phone_e164
        if customer.phone_verified_at is None:
            customer.onboarding_status = "pending_verification"
        customer.onboarding_source = entry_point

    if order is not None and customer is not None and order.customer_id is None:
        order.customer_id = customer.id

    token = generate_session_token()
    session = WhatsAppSession(
        order_id=order.id if order else None,
        customer_id=customer.id if customer else (order.customer_id if order else None),
        restaurant_id=restaurant_id,
        restaurant_name=restaurant_name,
        token_hash=hash_session_token(token, settings.session_token_pepper.get_secret_value()),
        token_hint=token_hint(token),
        entry_point=entry_point,
        intent=intent,
        resume_url=resume_url,
        provided_name=customer_name or (customer.display_name if customer else None),
        provided_phone=normalized_provided_phone or (customer.phone_e164 if customer else None),
        metadata_json=metadata or {},
        expires_at=utcnow() + timedelta(minutes=expires_in_minutes),
    )
    db.add(session)
    db.flush()

    order_reference = order.external_order_id or str(order.id) if order else entry_point
    prefilled_message = build_prefilled_message(token, restaurant_name, order_reference)
    return SessionLinkResponse(
        session_id=session.id,
        wa_url=build_wa_link(destination_number, prefilled_message),
        token_hint=session.token_hint,
        expires_at=session.expires_at,
    )
