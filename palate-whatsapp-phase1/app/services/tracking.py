from __future__ import annotations

from urllib.parse import quote
from uuid import UUID

from fastapi import Request
from sqlalchemy.orm import Session

from app.db.models import JourneyEvent, MessageLog, Order, WhatsAppSession


def request_ip_hint(request: Request | None) -> str | None:
    if request is None or request.client is None:
        return None
    return request.client.host


def request_user_agent(request: Request | None) -> str | None:
    if request is None:
        return None
    return request.headers.get("user-agent")


def build_tracked_url(
    base_url: str,
    target_url: str,
    *,
    stage: str,
    action: str,
    restaurant_id: str | None = None,
    order_id: UUID | None = None,
    session_id: UUID | None = None,
    message_log_id: UUID | None = None,
) -> str:
    query = [
        f"target={quote(target_url, safe='')}",
        f"stage={quote(stage, safe='')}",
        f"action={quote(action, safe='')}",
    ]
    if restaurant_id:
        query.append(f"restaurant_id={quote(restaurant_id, safe='')}")
    if order_id:
        query.append(f"order_id={order_id}")
    if session_id:
        query.append(f"session_id={session_id}")
    if message_log_id:
        query.append(f"message_log_id={message_log_id}")
    return f"{base_url.rstrip('/')}/r?{'&'.join(query)}"


def create_tracked_link(
    db: Session,
    base_url: str,
    target_url: str,
    *,
    stage: str,
    action: str,
    restaurant_id: str | None = None,
    order_id: UUID | None = None,
    session_id: UUID | None = None,
    message_log_id: UUID | None = None,
) -> str:
    event = log_journey_event(
        db,
        event_type="link_created",
        stage=stage,
        action=action,
        restaurant_id=restaurant_id,
        order_id=order_id,
        session_id=session_id,
        message_log_id=message_log_id,
        target_url=target_url,
    )
    db.flush()
    return f"{base_url.rstrip('/')}/r/{event.id}"


def log_journey_event(
    db: Session,
    *,
    event_type: str,
    stage: str | None = None,
    action: str | None = None,
    restaurant_id: str | None = None,
    order_id: UUID | None = None,
    session_id: UUID | None = None,
    message_log_id: UUID | None = None,
    target_url: str | None = None,
    request: Request | None = None,
    metadata: dict | None = None,
) -> JourneyEvent:
    event = JourneyEvent(
        event_type=event_type,
        stage=stage,
        action=action,
        restaurant_id=restaurant_id,
        order_id=order_id,
        session_id=session_id,
        message_log_id=message_log_id,
        target_url=target_url,
        user_agent=request_user_agent(request),
        ip_hint=request_ip_hint(request),
        metadata_json=metadata or {},
    )
    db.add(event)
    return event


def log_session_started(db: Session, session: WhatsAppSession, request: Request | None = None) -> JourneyEvent:
    return log_journey_event(
        db,
        event_type="session_started",
        stage=session.entry_point,
        action=session.intent,
        restaurant_id=session.restaurant_id,
        order_id=session.order_id,
        session_id=session.id,
        target_url=session.resume_url,
        request=request,
    )


def log_session_verified(db: Session, session: WhatsAppSession, request: Request | None = None) -> JourneyEvent:
    return log_journey_event(
        db,
        event_type="session_verified",
        stage=session.entry_point,
        action=session.intent,
        restaurant_id=session.restaurant_id,
        order_id=session.order_id,
        session_id=session.id,
        target_url=session.resume_url,
        request=request,
    )


def log_message_sent(
    db: Session,
    message_log: MessageLog,
    *,
    action: str | None,
    stage: str | None = None,
    request: Request | None = None,
) -> JourneyEvent:
    order: Order | None = message_log.order
    session: WhatsAppSession | None = message_log.whatsapp_session
    return log_journey_event(
        db,
        event_type="message_sent",
        stage=stage or (session.entry_point if session else None),
        action=action or message_log.message_type,
        restaurant_id=order.restaurant_id if order else (session.restaurant_id if session else None),
        order_id=message_log.order_id,
        session_id=message_log.session_id,
        message_log_id=message_log.id,
        request=request,
        metadata={"status": message_log.status, "provider": message_log.provider},
    )
