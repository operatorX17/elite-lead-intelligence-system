from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.exceptions import AppError
from app.core.security import normalize_phone
from app.db.models import Customer, MessageLog, Order, WhatsAppSession
from app.services.mock import MockWhatsAppClient
from app.services.meta import MetaWhatsAppClient
from app.services.tracking import log_journey_event, log_message_sent
from app.services.twilio import TwilioWhatsAppClient


def get_whatsapp_client(settings: Settings) -> tuple[object, str]:
    if settings.whatsapp_provider == "meta":
        return MetaWhatsAppClient(settings), "meta_whatsapp"
    if settings.whatsapp_provider == "twilio":
        return TwilioWhatsAppClient(settings), "twilio_whatsapp"
    if settings.whatsapp_provider == "mock":
        return MockWhatsAppClient(), "mock_whatsapp"
    raise AppError(503, "whatsapp_provider_invalid", f"Unsupported WHATSAPP_PROVIDER: {settings.whatsapp_provider}")


def _extract_provider_message_id(provider_name: str, response: dict[str, Any]) -> str | None:
    if provider_name == "twilio_whatsapp":
        return response.get("sid")
    return ((response.get("messages") or [{}])[0]).get("id")


def get_customer(db: Session, customer_id: UUID | None) -> Customer | None:
    if customer_id is None:
        return None
    return db.get(Customer, customer_id)


def get_order(db: Session, order_id: UUID | None) -> Order | None:
    if order_id is None:
        return None
    return db.get(Order, order_id)


def get_whatsapp_session(db: Session, session_id: UUID | None) -> WhatsAppSession | None:
    if session_id is None:
        return None
    return db.get(WhatsAppSession, session_id)


def find_latest_verified_session_for_order(db: Session, order_id: UUID | None) -> WhatsAppSession | None:
    if order_id is None:
        return None
    statement = (
        select(WhatsAppSession)
        .where(WhatsAppSession.order_id == order_id, WhatsAppSession.session_status == "verified")
        .order_by(WhatsAppSession.verified_at.desc(), WhatsAppSession.created_at.desc())
    )
    return db.execute(statement).scalar_one_or_none()


def resolve_target(
    db: Session,
    *,
    to_phone: str | None,
    customer_id: UUID | None,
    order_id: UUID | None,
    session_id: UUID | None,
    require_verified: bool,
) -> tuple[str, Customer | None, Order | None, WhatsAppSession | None]:
    normalized_direct_phone = normalize_phone(to_phone)
    customer = get_customer(db, customer_id)
    order = get_order(db, order_id)
    whatsapp_session = get_whatsapp_session(db, session_id)

    if order and customer is None:
        customer = order.customer
    if whatsapp_session and order is None:
        order = whatsapp_session.order
    if whatsapp_session and customer is None:
        customer = whatsapp_session.customer

    candidates: list[str | None] = []
    if normalized_direct_phone:
        candidates.append(normalized_direct_phone)
    if whatsapp_session and whatsapp_session.session_status == "verified":
        candidates.append(normalize_phone(whatsapp_session.phone_e164))
    if customer and customer.phone_verified_at:
        candidates.append(normalize_phone(customer.phone_e164))
    latest_verified_session = find_latest_verified_session_for_order(db, order.id if order else None)
    if latest_verified_session:
        whatsapp_session = latest_verified_session
        candidates.append(normalize_phone(latest_verified_session.phone_e164))

    resolved_phone = next((candidate for candidate in candidates if candidate), None)

    if resolved_phone is None and not require_verified and customer:
        resolved_phone = normalize_phone(customer.phone_e164)

    if resolved_phone is None:
        raise AppError(409, "phone_not_verified", "No verified WhatsApp phone is available for this resource")

    return resolved_phone, customer, order, whatsapp_session


def _build_preview(body: str | None) -> str | None:
    if body is None:
        return None
    preview = " ".join(body.split())
    return preview[:255]


async def send_text_and_log(
    db: Session,
    settings: Settings,
    *,
    to_phone: str,
    body: str,
    preview_url: bool,
    customer: Customer | None,
    order: Order | None,
    whatsapp_session: WhatsAppSession | None,
) -> MessageLog:
    client, provider_name = get_whatsapp_client(settings)
    try:
        response = await client.send_text_message(to_phone=to_phone, body=body, preview_url=preview_url)
        provider_message_id = _extract_provider_message_id(provider_name, response)
        message_log = MessageLog(
            order_id=order.id if order else None,
            customer_id=customer.id if customer else None,
            session_id=whatsapp_session.id if whatsapp_session else None,
            provider=provider_name,
            direction="outbound",
            message_type="text",
            meta_message_id=provider_message_id,
            provider_event_id=provider_message_id,
            recipient_phone=to_phone,
            status="accepted",
            content_preview=_build_preview(body),
            provider_payload={"preview_url": preview_url, "provider_response": response},
        )
        db.add(message_log)
        db.flush()
        log_message_sent(db, message_log, action="text")
        db.commit()
        db.refresh(message_log)
        return message_log
    except AppError as exc:
        db.rollback()
        failed_log = MessageLog(
            order_id=order.id if order else None,
            customer_id=customer.id if customer else None,
            session_id=whatsapp_session.id if whatsapp_session else None,
            provider=provider_name,
            direction="outbound",
            message_type="text",
            recipient_phone=to_phone,
            status="failed",
            content_preview=_build_preview(body),
            error_detail=exc.message,
        )
        db.add(failed_log)
        db.flush()
        log_journey_event(
            db,
            event_type="message_send_failed",
            stage=whatsapp_session.entry_point if whatsapp_session else None,
            action="text",
            restaurant_id=order.restaurant_id if order else (whatsapp_session.restaurant_id if whatsapp_session else None),
            order_id=order.id if order else None,
            session_id=whatsapp_session.id if whatsapp_session else None,
            message_log_id=failed_log.id,
            metadata={"provider": provider_name},
        )
        db.commit()
        raise


async def send_template_and_log(
    db: Session,
    settings: Settings,
    *,
    to_phone: str,
    template_name: str,
    language_code: str,
    components: list[dict[str, Any]],
    customer: Customer | None,
    order: Order | None,
    whatsapp_session: WhatsAppSession | None,
) -> MessageLog:
    client, provider_name = get_whatsapp_client(settings)
    try:
        response = await client.send_template_message(
            to_phone=to_phone,
            template_name=template_name,
            language_code=language_code,
            components=components,
        )
        provider_message_id = _extract_provider_message_id(provider_name, response)
        message_log = MessageLog(
            order_id=order.id if order else None,
            customer_id=customer.id if customer else None,
            session_id=whatsapp_session.id if whatsapp_session else None,
            provider=provider_name,
            direction="outbound",
            message_type="template",
            template_name=template_name,
            meta_message_id=provider_message_id,
            provider_event_id=provider_message_id,
            recipient_phone=to_phone,
            status="accepted",
            provider_payload={
                "language_code": language_code,
                "components_count": len(components),
                "provider_response": response,
            },
        )
        db.add(message_log)
        db.flush()
        log_message_sent(db, message_log, action=f"template:{template_name}")
        db.commit()
        db.refresh(message_log)
        return message_log
    except AppError as exc:
        db.rollback()
        failed_log = MessageLog(
            order_id=order.id if order else None,
            customer_id=customer.id if customer else None,
            session_id=whatsapp_session.id if whatsapp_session else None,
            provider=provider_name,
            direction="outbound",
            message_type="template",
            template_name=template_name,
            recipient_phone=to_phone,
            status="failed",
            error_detail=exc.message,
        )
        db.add(failed_log)
        db.flush()
        log_journey_event(
            db,
            event_type="message_send_failed",
            stage=whatsapp_session.entry_point if whatsapp_session else None,
            action=f"template:{template_name}",
            restaurant_id=order.restaurant_id if order else (whatsapp_session.restaurant_id if whatsapp_session else None),
            order_id=order.id if order else None,
            session_id=whatsapp_session.id if whatsapp_session else None,
            message_log_id=failed_log.id,
            metadata={"provider": provider_name},
        )
        db.commit()
        raise
