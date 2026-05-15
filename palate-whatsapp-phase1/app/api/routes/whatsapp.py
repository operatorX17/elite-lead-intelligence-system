from __future__ import annotations

from datetime import timezone
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_settings, require_internal_api_key
from app.core.config import Settings
from app.core.exceptions import AppError
from app.db.base import utcnow
from app.db.models import Customer, Order, WhatsAppSession
from app.schemas import (
    MessageResponse,
    SendMessageRequest,
    SendTemplateRequest,
    SessionLinkRequest,
    SessionLinkResponse,
    SessionStatusResponse,
)
from app.services.dispatch import resolve_target, send_template_and_log, send_text_and_log
from app.services.session_links import create_session_link_for_context
from app.services.template_helpers import build_template_components
from app.services.tracking import create_tracked_link, log_session_started

router = APIRouter(prefix="/api/v1/whatsapp", tags=["whatsapp"], dependencies=[Depends(require_internal_api_key)])


def _session_action(session_status: str) -> tuple[bool, bool, str, str]:
    if session_status == "verified":
        return True, True, "resume_flow", "Continue"
    if session_status == "expired":
        return False, False, "restart_verification", "Verify on WhatsApp"
    return False, False, "complete_whatsapp", "Open WhatsApp"


def _base_url(request: Request, settings: Settings) -> str:
    return settings.public_base_url.rstrip("/") if settings.public_base_url else str(request.base_url).rstrip("/")


def _resume_action_for_entry_point(entry_point: str) -> str:
    mapping = {
        "menu": "open_menu",
        "cart": "open_cart",
        "order_review": "view_order_review",
        "bill": "view_bill",
        "payment": "open_payment",
        "feedback": "open_feedback",
        "dish_review": "open_dish_review",
        "captain_pos": "open_captain_order",
    }
    return mapping.get(entry_point, "open_resume_link")


def _maybe_track_resume_url(
    db: Session,
    request: Request,
    settings: Settings,
    *,
    resume_url: str | None,
    entry_point: str,
    restaurant_id: str | None,
    order_id: UUID | None,
) -> str | None:
    if not resume_url:
        return None
    if "/r/" in resume_url or "/r?" in resume_url:
        return resume_url
    return create_tracked_link(
        db,
        _base_url(request, settings),
        resume_url,
        stage=entry_point,
        action=_resume_action_for_entry_point(entry_point),
        restaurant_id=restaurant_id,
        order_id=order_id,
    )


@router.post("/session-link", response_model=SessionLinkResponse)
def create_session_link(
    request: SessionLinkRequest,
    http_request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> SessionLinkResponse:
    order = db.get(Order, request.order_id) if request.order_id else None
    if request.order_id and order is None:
        raise AppError(404, "order_not_found", "Order not found")
    if order is None and request.external_order_id:
        order = db.execute(select(Order).where(Order.external_order_id == request.external_order_id)).scalar_one_or_none()

    customer = db.get(Customer, request.customer_id) if request.customer_id else None
    if request.customer_id and customer is None:
        raise AppError(404, "customer_not_found", "Customer not found")
    if customer is None and request.external_customer_id:
        customer = db.execute(select(Customer).where(Customer.external_customer_id == request.external_customer_id)).scalar_one_or_none()

    restaurant_id = order.restaurant_id if order else request.restaurant_id
    restaurant_name = order.restaurant_name if order else request.restaurant_name
    if not restaurant_id or not restaurant_name:
        raise AppError(
            422,
            "session_context_missing",
            "Provide either order_id or restaurant_id and restaurant_name to create a session link",
        )

    ttl_minutes = request.expires_in_minutes or settings.whatsapp_session_ttl_minutes
    tracked_resume_url = _maybe_track_resume_url(
        db,
        http_request,
        settings,
        resume_url=request.resume_url,
        entry_point=request.entry_point,
        restaurant_id=restaurant_id,
        order_id=order.id if order else None,
    )
    response = create_session_link_for_context(
        db,
        settings,
        order=order,
        customer=customer,
        restaurant_id=restaurant_id,
        restaurant_name=restaurant_name,
        customer_name=request.customer_name,
        provided_phone=request.provided_phone,
        entry_point=request.entry_point,
        intent=request.intent,
        resume_url=tracked_resume_url,
        metadata={
            "browser_session_id": request.browser_session_id,
            "cart_id": request.cart_id,
            "external_order_id": request.external_order_id,
            "external_customer_id": request.external_customer_id,
            "original_resume_url": request.resume_url,
        },
        expires_in_minutes=ttl_minutes,
    )
    session = db.get(WhatsAppSession, response.session_id)
    if session is not None:
        log_session_started(db, session, http_request)
    db.commit()
    return response


@router.get("/sessions/{session_id}", response_model=SessionStatusResponse)
def get_session_status(
    session_id: UUID,
    db: Session = Depends(get_db),
) -> SessionStatusResponse:
    session = db.get(WhatsAppSession, session_id)
    if session is None:
        raise AppError(404, "session_not_found", "WhatsApp session not found")

    current_status = session.session_status
    expires_at = session.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if current_status == "pending" and expires_at < utcnow():
        current_status = "expired"
    is_verified, can_proceed, next_action, recommended_cta_label = _session_action(current_status)

    return SessionStatusResponse(
        session_id=session.id,
        order_id=session.order_id,
        customer_id=session.customer_id,
        session_status=current_status,
        is_verified=is_verified,
        can_proceed=can_proceed,
        next_action=next_action,
        recommended_cta_label=recommended_cta_label,
        entry_point=session.entry_point,
        intent=session.intent,
        provided_name=session.provided_name,
        verified_phone=session.phone_e164,
        resume_url=session.resume_url,
        expires_at=session.expires_at,
        verified_at=session.verified_at,
    )


@router.post("/send-message", response_model=MessageResponse)
async def send_message(
    request: SendMessageRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> MessageResponse:
    require_verified = request.to_phone is None
    to_phone, customer, order, whatsapp_session = resolve_target(
        db,
        to_phone=request.to_phone,
        customer_id=request.customer_id,
        order_id=request.order_id,
        session_id=request.session_id,
        require_verified=require_verified,
    )
    message_log = await send_text_and_log(
        db,
        settings,
        to_phone=to_phone,
        body=request.body,
        preview_url=request.preview_url,
        customer=customer,
        order=order,
        whatsapp_session=whatsapp_session,
    )
    return MessageResponse(
        status=message_log.status,
        message_log_id=message_log.id,
        provider=message_log.provider,
        provider_message_id=message_log.provider_event_id or message_log.meta_message_id,
        meta_message_id=message_log.meta_message_id,
    )


@router.post("/send-template", response_model=MessageResponse)
async def send_template(
    request: SendTemplateRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> MessageResponse:
    require_verified = request.to_phone is None
    to_phone, customer, order, whatsapp_session = resolve_target(
        db,
        to_phone=request.to_phone,
        customer_id=request.customer_id,
        order_id=request.order_id,
        session_id=request.session_id,
        require_verified=require_verified,
    )
    components = request.components
    if request.template_helper and not components:
        if order is None:
            raise AppError(422, "template_helper_order_required", "order_id is required when using template_helper without components")
        try:
            components = build_template_components(request.template_helper, order)
        except ValueError as exc:
            raise AppError(422, "template_helper_invalid", str(exc))
    message_log = await send_template_and_log(
        db,
        settings,
        to_phone=to_phone,
        template_name=request.template_name,
        language_code=request.language_code,
        components=components,
        customer=customer,
        order=order,
        whatsapp_session=whatsapp_session,
    )
    return MessageResponse(
        status=message_log.status,
        message_log_id=message_log.id,
        provider=message_log.provider,
        provider_message_id=message_log.provider_event_id or message_log.meta_message_id,
        meta_message_id=message_log.meta_message_id,
    )
