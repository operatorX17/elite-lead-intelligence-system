"""add journey events

Revision ID: 20260429_0003
Revises: 20260426_0002
Create Date: 2026-04-29 16:55:00.000000
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260429_0003"
down_revision = "20260426_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "journey_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("stage", sa.String(length=32), nullable=True),
        sa.Column("action", sa.String(length=64), nullable=True),
        sa.Column("restaurant_id", sa.String(length=128), nullable=True),
        sa.Column("order_id", sa.Uuid(), nullable=True),
        sa.Column("session_id", sa.Uuid(), nullable=True),
        sa.Column("message_log_id", sa.Uuid(), nullable=True),
        sa.Column("target_url", sa.Text(), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("ip_hint", sa.String(length=64), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["message_log_id"], ["message_logs.id"], name=op.f("fk_journey_events_message_log_id_message_logs"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], name=op.f("fk_journey_events_order_id_orders"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["session_id"], ["whatsapp_sessions.id"], name=op.f("fk_journey_events_session_id_whatsapp_sessions"), ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_journey_events")),
    )
    op.create_index(op.f("ix_journey_events_action"), "journey_events", ["action"], unique=False)
    op.create_index(op.f("ix_journey_events_event_type"), "journey_events", ["event_type"], unique=False)
    op.create_index(op.f("ix_journey_events_message_log_id"), "journey_events", ["message_log_id"], unique=False)
    op.create_index(op.f("ix_journey_events_order_id"), "journey_events", ["order_id"], unique=False)
    op.create_index(op.f("ix_journey_events_restaurant_id"), "journey_events", ["restaurant_id"], unique=False)
    op.create_index(op.f("ix_journey_events_session_id"), "journey_events", ["session_id"], unique=False)
    op.create_index(op.f("ix_journey_events_stage"), "journey_events", ["stage"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_journey_events_stage"), table_name="journey_events")
    op.drop_index(op.f("ix_journey_events_session_id"), table_name="journey_events")
    op.drop_index(op.f("ix_journey_events_restaurant_id"), table_name="journey_events")
    op.drop_index(op.f("ix_journey_events_order_id"), table_name="journey_events")
    op.drop_index(op.f("ix_journey_events_message_log_id"), table_name="journey_events")
    op.drop_index(op.f("ix_journey_events_event_type"), table_name="journey_events")
    op.drop_index(op.f("ix_journey_events_action"), table_name="journey_events")
    op.drop_table("journey_events")
