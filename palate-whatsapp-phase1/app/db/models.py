from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, JSON, Numeric, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class Customer(TimestampMixin, Base):
    __tablename__ = "customers"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    external_customer_id: Mapped[str | None] = mapped_column(String(128), unique=True, nullable=True)
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone_e164: Mapped[str | None] = mapped_column(String(32), index=True, nullable=True)
    meta_wa_id: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True)
    onboarding_status: Mapped[str] = mapped_column(String(32), default="anonymous", index=True)
    onboarding_source: Mapped[str | None] = mapped_column(String(32), nullable=True)
    phone_verification_channel: Mapped[str | None] = mapped_column(String(32), nullable=True)
    phone_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    orders: Mapped[list["Order"]] = relationship(back_populates="customer")
    whatsapp_sessions: Mapped[list["WhatsAppSession"]] = relationship(back_populates="customer")


class Order(TimestampMixin, Base):
    __tablename__ = "orders"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    external_order_id: Mapped[str | None] = mapped_column(String(128), unique=True, nullable=True)
    customer_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("customers.id", ondelete="SET NULL"), index=True)
    restaurant_id: Mapped[str] = mapped_column(String(128), index=True)
    restaurant_name: Mapped[str] = mapped_column(String(255))
    order_status: Mapped[str] = mapped_column(String(32), default="created")
    currency: Mapped[str] = mapped_column(String(3), default="INR")
    subtotal_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    tax_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    total_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    amount_paid: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    summary_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    menu_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    order_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    bill_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    payment_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    feedback_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    line_items: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)

    customer: Mapped[Customer | None] = relationship(back_populates="orders")
    whatsapp_sessions: Mapped[list["WhatsAppSession"]] = relationship(back_populates="order")
    message_logs: Mapped[list["MessageLog"]] = relationship(back_populates="order")


class WhatsAppSession(TimestampMixin, Base):
    __tablename__ = "whatsapp_sessions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    order_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("orders.id", ondelete="SET NULL"), index=True)
    customer_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("customers.id", ondelete="SET NULL"), index=True)
    restaurant_id: Mapped[str] = mapped_column(String(128), index=True)
    restaurant_name: Mapped[str] = mapped_column(String(255))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    token_hint: Mapped[str] = mapped_column(String(12))
    session_status: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    entry_point: Mapped[str] = mapped_column(String(32), default="unknown", index=True)
    intent: Mapped[str] = mapped_column(String(32), default="verify_phone")
    resume_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    provided_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    provided_phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    phone_e164: Mapped[str | None] = mapped_column(String(32), nullable=True)
    meta_wa_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, default=dict)

    customer: Mapped[Customer | None] = relationship(back_populates="whatsapp_sessions")
    order: Mapped[Order | None] = relationship(back_populates="whatsapp_sessions")
    message_logs: Mapped[list["MessageLog"]] = relationship(back_populates="whatsapp_session")


class MessageLog(TimestampMixin, Base):
    __tablename__ = "message_logs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    order_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("orders.id", ondelete="SET NULL"), index=True)
    customer_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("customers.id", ondelete="SET NULL"), index=True)
    session_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("whatsapp_sessions.id", ondelete="SET NULL"), index=True)
    provider: Mapped[str] = mapped_column(String(32), default="meta_whatsapp")
    direction: Mapped[str] = mapped_column(String(16))
    message_type: Mapped[str] = mapped_column(String(32))
    template_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    meta_message_id: Mapped[str | None] = mapped_column(String(128), unique=True, nullable=True)
    provider_event_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    recipient_phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    sender_phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="accepted")
    content_preview: Mapped[str | None] = mapped_column(String(255), nullable=True)
    provider_payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    error_detail: Mapped[str | None] = mapped_column(Text, nullable=True)

    order: Mapped[Order | None] = relationship(back_populates="message_logs")
    whatsapp_session: Mapped[WhatsAppSession | None] = relationship(back_populates="message_logs")


class JourneyEvent(Base):
    __tablename__ = "journey_events"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    event_type: Mapped[str] = mapped_column(String(64), index=True)
    stage: Mapped[str | None] = mapped_column(String(32), index=True, nullable=True)
    action: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    restaurant_id: Mapped[str | None] = mapped_column(String(128), index=True, nullable=True)
    order_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("orders.id", ondelete="SET NULL"), index=True)
    session_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("whatsapp_sessions.id", ondelete="SET NULL"), index=True)
    message_log_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("message_logs.id", ondelete="SET NULL"), index=True)
    target_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    ip_hint: Mapped[str | None] = mapped_column(String(64), nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)


class WebhookEvent(Base):
    __tablename__ = "webhook_events"
    __table_args__ = (UniqueConstraint("provider", "event_key", name="uq_webhook_events_provider_event_key"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    provider: Mapped[str] = mapped_column(String(32), index=True)
    event_key: Mapped[str] = mapped_column(String(128), index=True)
    event_type: Mapped[str] = mapped_column(String(64))
    signature_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(32), default="accepted")
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)


class PaymentEvent(Base):
    __tablename__ = "payment_events"
    __table_args__ = (UniqueConstraint("provider", "event_key", name="uq_payment_events_provider_event_key"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    provider: Mapped[str] = mapped_column(String(32), default="razorpay", index=True)
    event_key: Mapped[str] = mapped_column(String(128), index=True)
    event_type: Mapped[str] = mapped_column(String(64))
    order_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("orders.id", ondelete="SET NULL"), index=True)
    payment_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    provider_order_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)


class IntegrationIntakeSubmission(TimestampMixin, Base):
    __tablename__ = "integration_intake_submissions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    project_key: Mapped[str] = mapped_column(String(64), default="palate_whatsapp_phase1", index=True)
    status: Mapped[str] = mapped_column(String(32), default="new", index=True)
    respondent_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    respondent_role: Mapped[str | None] = mapped_column(String(255), nullable=True)
    respondent_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    respondent_phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    provider_primary: Mapped[str | None] = mapped_column(String(32), nullable=True)
    provider_backup: Mapped[str | None] = mapped_column(String(32), nullable=True)
    real_urls: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    order_sources: Mapped[list[str]] = mapped_column(JSON, default=list)
    verification_points: Mapped[list[str]] = mapped_column(JSON, default=list)
    customer_inputs: Mapped[list[str]] = mapped_column(JSON, default=list)
    canonical_order_reference: Mapped[str | None] = mapped_column(Text, nullable=True)
    payment_provider: Mapped[str | None] = mapped_column(String(64), nullable=True)
    payment_mapping_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    required_messages: Mapped[list[str]] = mapped_column(JSON, default=list)
    messaging_rules_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    production_domain: Mapped[str | None] = mapped_column(Text, nullable=True)
    ownership: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    final_flow_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    general_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
