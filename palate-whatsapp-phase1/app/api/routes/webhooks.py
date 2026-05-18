from __future__ import annotations

import asyncio
import hashlib
import json
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import PlainTextResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_settings
from app.core.config import Settings
from app.core.exceptions import AppError
from app.core.security import (
    normalize_phone,
    verify_meta_signature,
    verify_razorpay_signature,
    verify_twilio_signature,
)
from app.db.models import Customer, MessageLog, Order, PaymentEvent, WebhookEvent, WhatsAppSession
from app.services.dispatch import resolve_target, send_text_and_log
from app.services.first_session_message import compose_first_session_followup, should_send_first_session_welcome
from app.services.orders import compose_payment_failed_message, compose_payment_success_message, compose_post_verification_message
from app.services.session_tokens import extract_session_token, hash_session_token
from app.services.tracking import log_journey_event, log_session_verified

router = APIRouter(tags=["webhooks"])

FIRST_SESSION_FOLLOWUP_DELAY_SECONDS = 10


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _request_url_for_signature(request: Request, settings: Settings) -> str:
    base_url = settings.public_base_url.rstrip("/") if settings.public_base_url else str(request.base_url).rstrip("/")
    return f"{base_url}{request.url.path}" + (f"?{request.url.query}" if request.url.query else "")


def _empty_twiml_response() -> Response:
    return Response(
        content='<?xml version="1.0" encoding="UTF-8"?><Response></Response>',
        media_type="application/xml",
    )


def _upsert_meta_status_log(
    db: Session,
    *,
    message_id: str,
    status_value: str,
    payload: dict[str, Any],
) -> None:
    statement = select(MessageLog).where(MessageLog.meta_message_id == message_id)
    message_log = db.execute(statement).scalar_one_or_none()
    if message_log is None:
        message_log = MessageLog(
            provider="meta_whatsapp",
            direction="outbound",
            message_type="status",
            meta_message_id=message_id,
            provider_event_id=message_id,
            status=status_value,
            provider_payload=payload,
        )
        db.add(message_log)
        return

    message_log.status = status_value
    message_log.provider_payload = payload


def _log_inbound_message(
    db: Session,
    *,
    provider: str,
    order: Order | None,
    customer: Customer | None,
    whatsapp_session: WhatsAppSession | None,
    sender_phone: str | None,
    inbound_message_id: str | None,
    body: str,
    provider_payload: dict[str, Any] | None = None,
) -> None:
    if inbound_message_id:
        existing = db.execute(select(MessageLog).where(MessageLog.meta_message_id == inbound_message_id)).scalar_one_or_none()
        if existing is not None:
            return

    db.add(
        MessageLog(
            order_id=order.id if order else None,
            customer_id=customer.id if customer else None,
            session_id=whatsapp_session.id if whatsapp_session else None,
            provider=provider,
            direction="inbound",
            message_type="text",
            meta_message_id=inbound_message_id,
            provider_event_id=inbound_message_id,
            sender_phone=sender_phone,
            status="received",
            content_preview=" ".join(body.split())[:255],
            provider_payload=provider_payload or {},
        )
    )


def _find_order_by_reference(db: Session, reference: str | None) -> Order | None:
    if reference is None:
        return None
    try:
        order = db.get(Order, reference)
        if order is not None:
            return order
    except Exception:
        pass
    statement = select(Order).where(Order.external_order_id == reference)
    return db.execute(statement).scalar_one_or_none()


def _find_existing_customer_for_verified_sender(
    db: Session,
    *,
    sender_phone: str | None,
    provider: str,
    provider_user_id: str | None,
) -> Customer | None:
    if provider == "meta_whatsapp" and provider_user_id:
        statement = (
            select(Customer)
            .where(Customer.meta_wa_id == provider_user_id)
            .order_by(Customer.phone_verified_at.desc(), Customer.updated_at.desc(), Customer.created_at.desc())
            .limit(1)
        )
        customer = db.execute(statement).scalar_one_or_none()
        if customer is not None:
            return customer
    if sender_phone:
        statement = (
            select(Customer)
            .where(Customer.phone_e164 == sender_phone)
            .order_by(Customer.phone_verified_at.desc(), Customer.updated_at.desc(), Customer.created_at.desc())
            .limit(1)
        )
        customer = db.execute(statement).scalar_one_or_none()
        if customer is not None:
            return customer
    return None


def _provider_profile_name(payload: dict[str, Any]) -> str | None:
    for key in ("ProfileName", "profile_name", "pushName"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    profile = payload.get("profile")
    if isinstance(profile, dict):
        value = profile.get("name")
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


async def _process_inbound_verification_message(
    db: Session,
    settings: Settings,
    *,
    provider: str,
    sender_phone: str | None,
    inbound_message_id: str | None,
    body: str,
    provider_user_id: str | None,
    provider_payload: dict[str, Any],
) -> None:
    token = extract_session_token(body)
    resolved_session = None
    resolved_order = None
    resolved_customer = None

    if token and settings.session_token_pepper is not None:
        token_hash = hash_session_token(token, settings.session_token_pepper.get_secret_value())
        statement = select(WhatsAppSession).where(WhatsAppSession.token_hash == token_hash)
        resolved_session = db.execute(statement).scalar_one_or_none()

        if (
            resolved_session is not None
            and resolved_session.session_status in {"pending", "verified"}
            and (_as_utc(resolved_session.expires_at) or datetime.min.replace(tzinfo=timezone.utc)) >= _now_utc()
        ):
            session_metadata = dict(resolved_session.metadata_json or {})
            should_send_reply = session_metadata.get("post_verification_message_sent") is not True
            resolved_session.phone_e164 = sender_phone
            resolved_session.session_status = "verified"
            resolved_session.verified_at = _now_utc()
            if provider == "meta_whatsapp" and provider_user_id:
                resolved_session.meta_wa_id = provider_user_id
            resolved_session.metadata_json = {
                **session_metadata,
                "last_verified_provider": provider,
                "provider_user_id": provider_user_id,
            }
            resolved_order = resolved_session.order
            resolved_customer = resolved_session.customer or _find_existing_customer_for_verified_sender(
                db,
                sender_phone=sender_phone,
                provider=provider,
                provider_user_id=provider_user_id,
            )

            if resolved_customer is None:
                resolved_customer = Customer(
                    display_name=resolved_session.provided_name or _provider_profile_name(provider_payload),
                    phone_e164=sender_phone or resolved_session.provided_phone,
                    meta_wa_id=provider_user_id if provider == "meta_whatsapp" else None,
                    onboarding_status="verified",
                    onboarding_source=resolved_session.entry_point,
                    phone_verification_channel="whatsapp",
                    phone_verified_at=_now_utc(),
                )
                db.add(resolved_customer)
                db.flush()
            if resolved_customer is not None and resolved_session.customer_id is None:
                resolved_session.customer_id = resolved_customer.id

            profile_name = _provider_profile_name(provider_payload)
            resolved_customer.display_name = resolved_customer.display_name or resolved_session.provided_name or profile_name
            resolved_session.provided_name = resolved_session.provided_name or profile_name
            resolved_customer.phone_e164 = sender_phone or resolved_customer.phone_e164
            if provider == "meta_whatsapp" and provider_user_id:
                resolved_customer.meta_wa_id = provider_user_id
            resolved_customer.onboarding_status = "verified"
            resolved_customer.onboarding_source = resolved_session.entry_point
            resolved_customer.phone_verification_channel = "whatsapp"
            resolved_customer.phone_verified_at = _now_utc()

            if resolved_order is not None and resolved_customer is not None and resolved_order.customer_id is None:
                resolved_order.customer_id = resolved_customer.id

            log_session_verified(db, resolved_session)

            _log_inbound_message(
                db,
                provider=provider,
                order=resolved_order,
                customer=resolved_customer,
                whatsapp_session=resolved_session,
                sender_phone=sender_phone,
                inbound_message_id=inbound_message_id,
                body=body,
                provider_payload=provider_payload,
            )
            db.commit()
            if should_send_reply:
                is_first_session_welcome = resolved_order is None and should_send_first_session_welcome(resolved_session)
                await send_text_and_log(
                    db,
                    settings,
                    to_phone=sender_phone or "",
                    body=compose_post_verification_message(resolved_order, resolved_session),
                    preview_url=True,
                    customer=resolved_customer,
                    order=resolved_order,
                    whatsapp_session=resolved_session,
                )
                if is_first_session_welcome:
                    await asyncio.sleep(FIRST_SESSION_FOLLOWUP_DELAY_SECONDS)
                    await send_text_and_log(
                        db,
                        settings,
                        to_phone=sender_phone or "",
                        body=compose_first_session_followup(),
                        preview_url=False,
                        customer=resolved_customer,
                        order=resolved_order,
                        whatsapp_session=resolved_session,
                    )
                resolved_session.metadata_json = {
                    **(resolved_session.metadata_json or {}),
                    "post_verification_message_sent": True,
                    "post_verification_message_sent_at": _now_utc().isoformat(),
                }
                db.commit()
            return

    _log_inbound_message(
        db,
        provider=provider,
        order=resolved_order,
        customer=resolved_customer,
        whatsapp_session=resolved_session,
        sender_phone=sender_phone,
        inbound_message_id=inbound_message_id,
        body=body,
        provider_payload=provider_payload,
    )
    db.commit()


@router.get("/webhooks/meta/whatsapp")
def verify_meta_webhook(request: Request, settings: Settings = Depends(get_settings)) -> PlainTextResponse:
    mode = request.query_params.get("hub.mode")
    challenge = request.query_params.get("hub.challenge")
    verify_token = request.query_params.get("hub.verify_token")

    if settings.meta_verify_token is None:
        raise AppError(503, "meta_verify_token_missing", "META_VERIFY_TOKEN is not configured")

    if mode != "subscribe" or verify_token != settings.meta_verify_token.get_secret_value():
        raise AppError(403, "meta_verification_failed", "Meta webhook verification failed")
    if challenge is None:
        raise AppError(400, "meta_challenge_missing", "hub.challenge is required")

    return PlainTextResponse(challenge)


@router.post("/webhooks/meta/whatsapp")
async def receive_meta_webhook(
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    if settings.meta_app_secret is None:
        raise AppError(503, "meta_app_secret_missing", "META_APP_SECRET is not configured")

    raw_body = await request.body()
    signature = request.headers.get("X-Hub-Signature-256")
    if not verify_meta_signature(signature, raw_body, settings.meta_app_secret.get_secret_value()):
        raise AppError(401, "meta_signature_invalid", "Invalid Meta webhook signature")

    payload = json.loads(raw_body.decode("utf-8"))
    event_key = hashlib.sha256(raw_body).hexdigest()
    existing_event = db.execute(
        select(WebhookEvent).where(WebhookEvent.provider == "meta_whatsapp", WebhookEvent.event_key == event_key)
    ).scalar_one_or_none()
    if existing_event is not None:
        return {"status": "duplicate", "event_id": str(existing_event.id)}

    webhook_event = WebhookEvent(
        provider="meta_whatsapp",
        event_key=event_key,
        event_type=payload.get("object", "whatsapp"),
        signature_verified=True,
        status="accepted",
        payload=payload,
    )
    db.add(webhook_event)
    db.flush()

    processed_messages = 0
    processed_statuses = 0

    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value") or {}
            contacts_by_wa_id = {
                str(contact.get("wa_id")): contact
                for contact in value.get("contacts", [])
                if isinstance(contact, dict) and contact.get("wa_id")
            }

            for status_payload in value.get("statuses", []):
                message_id = status_payload.get("id")
                if message_id:
                    _upsert_meta_status_log(
                        db,
                        message_id=message_id,
                        status_value=status_payload.get("status", "unknown"),
                        payload=status_payload,
                    )
                    processed_statuses += 1

            for message_payload in value.get("messages", []):
                processed_messages += 1
                sender_phone = normalize_phone(message_payload.get("from"))
                contact_payload = contacts_by_wa_id.get(str(message_payload.get("from")), {})
                profile_payload = contact_payload.get("profile") if isinstance(contact_payload, dict) else None
                provider_payload = {
                    **message_payload,
                    **({"profile": profile_payload} if isinstance(profile_payload, dict) else {}),
                }
                body = ""
                if message_payload.get("type") == "text":
                    body = (message_payload.get("text") or {}).get("body", "")
                await _process_inbound_verification_message(
                    db,
                    settings,
                    provider="meta_whatsapp",
                    sender_phone=sender_phone,
                    inbound_message_id=message_payload.get("id"),
                    body=body,
                    provider_user_id=message_payload.get("from"),
                    provider_payload=provider_payload,
                )

    webhook_event.status = "processed"
    webhook_event.processed_at = _now_utc()
    db.commit()

    return {
        "status": "ok",
        "processed_messages": processed_messages,
        "processed_statuses": processed_statuses,
    }


@router.post("/webhooks/twilio/whatsapp")
async def receive_twilio_whatsapp_webhook(
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> Response:
    if settings.whatsapp_provider != "twilio":
        raise AppError(409, "twilio_provider_inactive", "Twilio WhatsApp webhook is inactive unless WHATSAPP_PROVIDER=twilio")

    form = await request.form()
    payload = {key: str(value) for key, value in form.items()}
    message_sid = payload.get("MessageSid")
    body = payload.get("Body", "")
    sender_phone = normalize_phone(payload.get("From", "").replace("whatsapp:", ""))
    recipient_phone = normalize_phone(payload.get("To", "").replace("whatsapp:", ""))

    if settings.twilio_webhook_auth_enabled:
        if settings.twilio_auth_token is None:
            raise AppError(503, "twilio_auth_token_missing", "TWILIO_AUTH_TOKEN is not configured")
        signature = request.headers.get("X-Twilio-Signature")
        signature_url = _request_url_for_signature(request, settings)
        if not verify_twilio_signature(signature, signature_url, payload, settings.twilio_auth_token.get_secret_value()):
            raise AppError(401, "twilio_signature_invalid", "Invalid Twilio webhook signature")

    event_key = message_sid or hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()
    existing_event = db.execute(
        select(WebhookEvent).where(WebhookEvent.provider == "twilio_whatsapp", WebhookEvent.event_key == event_key)
    ).scalar_one_or_none()
    if existing_event is not None:
        return _empty_twiml_response()

    webhook_event = WebhookEvent(
        provider="twilio_whatsapp",
        event_key=event_key,
        event_type="incoming_message",
        signature_verified=bool(settings.twilio_webhook_auth_enabled),
        status="accepted",
        payload=payload,
    )
    db.add(webhook_event)
    db.flush()

    await _process_inbound_verification_message(
        db,
        settings,
        provider="twilio_whatsapp",
        sender_phone=sender_phone,
        inbound_message_id=message_sid,
        body=body,
        provider_user_id=payload.get("WaId"),
        provider_payload={**payload, "recipient_phone": recipient_phone},
    )

    webhook_event.status = "processed"
    webhook_event.processed_at = _now_utc()
    db.commit()
    return _empty_twiml_response()


@router.post("/webhooks/payments/razorpay")
async def receive_razorpay_webhook(
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    if settings.razorpay_webhook_secret is None:
        raise AppError(503, "razorpay_secret_missing", "RAZORPAY_WEBHOOK_SECRET is not configured")

    raw_body = await request.body()
    signature = request.headers.get("X-Razorpay-Signature")
    if not verify_razorpay_signature(signature, raw_body, settings.razorpay_webhook_secret.get_secret_value()):
        raise AppError(401, "razorpay_signature_invalid", "Invalid Razorpay webhook signature")

    payload = json.loads(raw_body.decode("utf-8"))
    event_key = request.headers.get("x-razorpay-event-id") or hashlib.sha256(raw_body).hexdigest()

    existing_event = db.execute(
        select(WebhookEvent).where(WebhookEvent.provider == "razorpay", WebhookEvent.event_key == event_key)
    ).scalar_one_or_none()
    if existing_event is not None:
        return {"status": "duplicate", "event_id": str(existing_event.id)}

    webhook_event = WebhookEvent(
        provider="razorpay",
        event_key=event_key,
        event_type=payload.get("event", "unknown"),
        signature_verified=True,
        status="accepted",
        payload=payload,
    )
    db.add(webhook_event)
    db.flush()

    payment_entity = ((payload.get("payload") or {}).get("payment") or {}).get("entity") or {}
    notes = payment_entity.get("notes") or {}
    order = _find_order_by_reference(db, notes.get("order_id")) or _find_order_by_reference(db, notes.get("external_order_id"))

    payment_event = PaymentEvent(
        provider="razorpay",
        event_key=event_key,
        event_type=payload.get("event", "unknown"),
        order_id=order.id if order else None,
        payment_id=payment_entity.get("id"),
        provider_order_id=payment_entity.get("order_id"),
        amount=(Decimal(str(payment_entity["amount"])) / Decimal("100")) if payment_entity.get("amount") is not None else None,
        currency=payment_entity.get("currency"),
        payload=payload,
        processed_at=_now_utc(),
    )
    db.add(payment_event)

    payment_status_message: str | None = None
    payment_event_type = payload.get("event")

    if order is not None and payment_event.amount is not None:
        order.amount_paid = payment_event.amount
        if payment_event_type in {"payment.captured", "order.paid", "payment_link.paid"}:
            order.order_status = "paid"
            payment_status_message = compose_payment_success_message(order)
            log_journey_event(
                db,
                event_type="payment_confirmed",
                stage="payment",
                action=payment_event_type,
                restaurant_id=order.restaurant_id,
                order_id=order.id,
                target_url=order.payment_url,
                metadata={
                    "provider": "razorpay",
                    "payment_id": payment_event.payment_id,
                    "amount": str(payment_event.amount),
                },
            )
        elif payment_event_type in {"payment.failed", "payment_link.cancelled"}:
            order.order_status = "payment_failed"
            payment_status_message = compose_payment_failed_message(order)
            log_journey_event(
                db,
                event_type="payment_failed",
                stage="payment",
                action=payment_event_type,
                restaurant_id=order.restaurant_id,
                order_id=order.id,
                target_url=order.payment_url,
                metadata={
                    "provider": "razorpay",
                    "payment_id": payment_event.payment_id,
                    "amount": str(payment_event.amount),
                },
            )

    webhook_event.status = "processed"
    webhook_event.processed_at = _now_utc()
    db.commit()

    if order is not None and payment_status_message:
        try:
            to_phone, customer, _, whatsapp_session = resolve_target(
                db,
                to_phone=None,
                customer_id=order.customer_id,
                order_id=order.id,
                session_id=None,
                require_verified=True,
            )
            await send_text_and_log(
                db,
                settings,
                to_phone=to_phone,
                body=payment_status_message,
                preview_url=True,
                customer=customer,
                order=order,
                whatsapp_session=whatsapp_session,
            )
        except AppError as exc:
            log_journey_event(
                db,
                event_type="payment_message_skipped",
                stage="payment",
                action=payment_event_type,
                restaurant_id=order.restaurant_id,
                order_id=order.id,
                target_url=order.payment_url,
                metadata={"reason": exc.code},
            )
            db.commit()

    return {"status": "ok", "payment_event_id": str(payment_event.id)}
