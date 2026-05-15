from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_settings, require_internal_api_key
from app.core.config import Settings
from app.core.exceptions import AppError
from app.db.models import Order
from app.schemas import MessageResponse, OrderMessageRequest
from app.services.dispatch import resolve_target, send_template_and_log, send_text_and_log
from app.services.orders import compose_bill_message, compose_feedback_message, compose_order_summary
from app.services.template_helpers import build_template_components

router = APIRouter(prefix="/api/v1/orders", tags=["orders"], dependencies=[Depends(require_internal_api_key)])


def _get_order_or_404(db: Session, order_id: UUID) -> Order:
    order = db.get(Order, order_id)
    if order is None:
        raise AppError(404, "order_not_found", "Order not found")
    return order


@router.post("/{order_id}/send-whatsapp-summary", response_model=MessageResponse)
async def send_whatsapp_summary(
    order_id: UUID,
    request: OrderMessageRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> MessageResponse:
    order = _get_order_or_404(db, order_id)
    to_phone, customer, _, whatsapp_session = resolve_target(
        db,
        to_phone=None,
        customer_id=order.customer_id,
        order_id=order.id,
        session_id=None,
        require_verified=True,
    )
    if request.template_name:
        components = request.components
        if request.template_helper and not components:
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
    else:
        message_log = await send_text_and_log(
            db,
            settings,
            to_phone=to_phone,
            body=compose_order_summary(order),
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


@router.post("/{order_id}/send-bill", response_model=MessageResponse)
async def send_bill(
    order_id: UUID,
    request: OrderMessageRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> MessageResponse:
    order = _get_order_or_404(db, order_id)
    to_phone, customer, _, whatsapp_session = resolve_target(
        db,
        to_phone=None,
        customer_id=order.customer_id,
        order_id=order.id,
        session_id=None,
        require_verified=True,
    )
    if request.template_name:
        components = request.components
        if request.template_helper and not components:
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
    else:
        message_log = await send_text_and_log(
            db,
            settings,
            to_phone=to_phone,
            body=compose_bill_message(order),
            preview_url=True,
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


@router.post("/{order_id}/send-feedback", response_model=MessageResponse)
async def send_feedback(
    order_id: UUID,
    request: OrderMessageRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> MessageResponse:
    order = _get_order_or_404(db, order_id)
    to_phone, customer, _, whatsapp_session = resolve_target(
        db,
        to_phone=None,
        customer_id=order.customer_id,
        order_id=order.id,
        session_id=None,
        require_verified=True,
    )
    if request.template_name:
        components = request.components
        if request.template_helper and not components:
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
    else:
        message_log = await send_text_and_log(
            db,
            settings,
            to_phone=to_phone,
            body=compose_feedback_message(order),
            preview_url=True,
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
