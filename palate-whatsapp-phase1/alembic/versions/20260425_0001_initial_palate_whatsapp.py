"""create phase 1 whatsapp schema

Revision ID: 20260425_0001
Revises:
Create Date: 2026-04-25 18:10:00.000000
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260425_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "customers",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("external_customer_id", sa.String(length=128), nullable=True),
        sa.Column("display_name", sa.String(length=255), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("phone_e164", sa.String(length=32), nullable=True),
        sa.Column("meta_wa_id", sa.String(length=64), nullable=True),
        sa.Column("onboarding_status", sa.String(length=32), nullable=False),
        sa.Column("onboarding_source", sa.String(length=32), nullable=True),
        sa.Column("phone_verification_channel", sa.String(length=32), nullable=True),
        sa.Column("phone_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_customers")),
        sa.UniqueConstraint("external_customer_id", name=op.f("uq_customers_external_customer_id")),
        sa.UniqueConstraint("meta_wa_id", name=op.f("uq_customers_meta_wa_id")),
    )
    op.create_index(op.f("ix_customers_onboarding_status"), "customers", ["onboarding_status"], unique=False)
    op.create_index(op.f("ix_phone_e164"), "customers", ["phone_e164"], unique=False)

    op.create_table(
        "orders",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("external_order_id", sa.String(length=128), nullable=True),
        sa.Column("customer_id", sa.Uuid(), nullable=True),
        sa.Column("restaurant_id", sa.String(length=128), nullable=False),
        sa.Column("restaurant_name", sa.String(length=255), nullable=False),
        sa.Column("order_status", sa.String(length=32), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("subtotal_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("tax_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("total_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("amount_paid", sa.Numeric(12, 2), nullable=True),
        sa.Column("summary_text", sa.Text(), nullable=True),
        sa.Column("menu_url", sa.Text(), nullable=True),
        sa.Column("order_url", sa.Text(), nullable=True),
        sa.Column("bill_url", sa.Text(), nullable=True),
        sa.Column("payment_url", sa.Text(), nullable=True),
        sa.Column("feedback_url", sa.Text(), nullable=True),
        sa.Column("notes", sa.JSON(), nullable=False),
        sa.Column("line_items", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], name=op.f("fk_orders_customer_id_customers"), ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_orders")),
        sa.UniqueConstraint("external_order_id", name=op.f("uq_orders_external_order_id")),
    )
    op.create_index(op.f("ix_orders_customer_id"), "orders", ["customer_id"], unique=False)
    op.create_index(op.f("ix_orders_restaurant_id"), "orders", ["restaurant_id"], unique=False)

    op.create_table(
        "whatsapp_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("order_id", sa.Uuid(), nullable=True),
        sa.Column("customer_id", sa.Uuid(), nullable=True),
        sa.Column("restaurant_id", sa.String(length=128), nullable=False),
        sa.Column("restaurant_name", sa.String(length=255), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("token_hint", sa.String(length=12), nullable=False),
        sa.Column("session_status", sa.String(length=32), nullable=False),
        sa.Column("entry_point", sa.String(length=32), nullable=False),
        sa.Column("intent", sa.String(length=32), nullable=False),
        sa.Column("resume_url", sa.Text(), nullable=True),
        sa.Column("provided_name", sa.String(length=255), nullable=True),
        sa.Column("provided_phone", sa.String(length=32), nullable=True),
        sa.Column("phone_e164", sa.String(length=32), nullable=True),
        sa.Column("meta_wa_id", sa.String(length=64), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], name=op.f("fk_whatsapp_sessions_customer_id_customers"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], name=op.f("fk_whatsapp_sessions_order_id_orders"), ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_whatsapp_sessions")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_whatsapp_sessions_token_hash")),
    )
    op.create_index(op.f("ix_whatsapp_sessions_customer_id"), "whatsapp_sessions", ["customer_id"], unique=False)
    op.create_index(op.f("ix_whatsapp_sessions_entry_point"), "whatsapp_sessions", ["entry_point"], unique=False)
    op.create_index(op.f("ix_whatsapp_sessions_expires_at"), "whatsapp_sessions", ["expires_at"], unique=False)
    op.create_index(op.f("ix_whatsapp_sessions_order_id"), "whatsapp_sessions", ["order_id"], unique=False)
    op.create_index(op.f("ix_whatsapp_sessions_session_status"), "whatsapp_sessions", ["session_status"], unique=False)
    op.create_index(op.f("ix_whatsapp_sessions_token_hash"), "whatsapp_sessions", ["token_hash"], unique=False)

    op.create_table(
        "message_logs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("order_id", sa.Uuid(), nullable=True),
        sa.Column("customer_id", sa.Uuid(), nullable=True),
        sa.Column("session_id", sa.Uuid(), nullable=True),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("direction", sa.String(length=16), nullable=False),
        sa.Column("message_type", sa.String(length=32), nullable=False),
        sa.Column("template_name", sa.String(length=255), nullable=True),
        sa.Column("meta_message_id", sa.String(length=128), nullable=True),
        sa.Column("provider_event_id", sa.String(length=128), nullable=True),
        sa.Column("recipient_phone", sa.String(length=32), nullable=True),
        sa.Column("sender_phone", sa.String(length=32), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("content_preview", sa.String(length=255), nullable=True),
        sa.Column("provider_payload", sa.JSON(), nullable=False),
        sa.Column("error_detail", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], name=op.f("fk_message_logs_customer_id_customers"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], name=op.f("fk_message_logs_order_id_orders"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["session_id"], ["whatsapp_sessions.id"], name=op.f("fk_message_logs_session_id_whatsapp_sessions"), ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_message_logs")),
        sa.UniqueConstraint("meta_message_id", name=op.f("uq_message_logs_meta_message_id")),
    )
    op.create_index(op.f("ix_message_logs_customer_id"), "message_logs", ["customer_id"], unique=False)
    op.create_index(op.f("ix_message_logs_order_id"), "message_logs", ["order_id"], unique=False)
    op.create_index(op.f("ix_message_logs_session_id"), "message_logs", ["session_id"], unique=False)

    op.create_table(
        "webhook_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("event_key", sa.String(length=128), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("signature_verified", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_webhook_events")),
        sa.UniqueConstraint("provider", "event_key", name="uq_webhook_events_provider_event_key"),
    )
    op.create_index(op.f("ix_webhook_events_event_key"), "webhook_events", ["event_key"], unique=False)
    op.create_index(op.f("ix_webhook_events_provider"), "webhook_events", ["provider"], unique=False)

    op.create_table(
        "payment_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("event_key", sa.String(length=128), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("order_id", sa.Uuid(), nullable=True),
        sa.Column("payment_id", sa.String(length=128), nullable=True),
        sa.Column("provider_order_id", sa.String(length=128), nullable=True),
        sa.Column("amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], name=op.f("fk_payment_events_order_id_orders"), ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_payment_events")),
        sa.UniqueConstraint("provider", "event_key", name="uq_payment_events_provider_event_key"),
    )
    op.create_index(op.f("ix_payment_events_event_key"), "payment_events", ["event_key"], unique=False)
    op.create_index(op.f("ix_payment_events_order_id"), "payment_events", ["order_id"], unique=False)
    op.create_index(op.f("ix_payment_events_provider"), "payment_events", ["provider"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_payment_events_provider"), table_name="payment_events")
    op.drop_index(op.f("ix_payment_events_order_id"), table_name="payment_events")
    op.drop_index(op.f("ix_payment_events_event_key"), table_name="payment_events")
    op.drop_table("payment_events")

    op.drop_index(op.f("ix_webhook_events_provider"), table_name="webhook_events")
    op.drop_index(op.f("ix_webhook_events_event_key"), table_name="webhook_events")
    op.drop_table("webhook_events")

    op.drop_index(op.f("ix_message_logs_session_id"), table_name="message_logs")
    op.drop_index(op.f("ix_message_logs_order_id"), table_name="message_logs")
    op.drop_index(op.f("ix_message_logs_customer_id"), table_name="message_logs")
    op.drop_table("message_logs")

    op.drop_index(op.f("ix_whatsapp_sessions_token_hash"), table_name="whatsapp_sessions")
    op.drop_index(op.f("ix_whatsapp_sessions_session_status"), table_name="whatsapp_sessions")
    op.drop_index(op.f("ix_whatsapp_sessions_order_id"), table_name="whatsapp_sessions")
    op.drop_index(op.f("ix_whatsapp_sessions_entry_point"), table_name="whatsapp_sessions")
    op.drop_index(op.f("ix_whatsapp_sessions_expires_at"), table_name="whatsapp_sessions")
    op.drop_index(op.f("ix_whatsapp_sessions_customer_id"), table_name="whatsapp_sessions")
    op.drop_table("whatsapp_sessions")

    op.drop_index(op.f("ix_orders_restaurant_id"), table_name="orders")
    op.drop_index(op.f("ix_orders_customer_id"), table_name="orders")
    op.drop_table("orders")

    op.drop_index(op.f("ix_customers_onboarding_status"), table_name="customers")
    op.drop_index(op.f("ix_phone_e164"), table_name="customers")
    op.drop_table("customers")
