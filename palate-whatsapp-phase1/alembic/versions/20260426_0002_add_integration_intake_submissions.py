"""add integration intake submissions

Revision ID: 20260426_0002
Revises: 20260425_0001
Create Date: 2026-04-26 16:55:00.000000
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260426_0002"
down_revision = "20260425_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "integration_intake_submissions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_key", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("respondent_name", sa.String(length=255), nullable=True),
        sa.Column("respondent_role", sa.String(length=255), nullable=True),
        sa.Column("respondent_email", sa.String(length=255), nullable=True),
        sa.Column("respondent_phone", sa.String(length=32), nullable=True),
        sa.Column("provider_primary", sa.String(length=32), nullable=True),
        sa.Column("provider_backup", sa.String(length=32), nullable=True),
        sa.Column("real_urls", sa.JSON(), nullable=False),
        sa.Column("order_sources", sa.JSON(), nullable=False),
        sa.Column("verification_points", sa.JSON(), nullable=False),
        sa.Column("customer_inputs", sa.JSON(), nullable=False),
        sa.Column("canonical_order_reference", sa.Text(), nullable=True),
        sa.Column("payment_provider", sa.String(length=64), nullable=True),
        sa.Column("payment_mapping_notes", sa.Text(), nullable=True),
        sa.Column("required_messages", sa.JSON(), nullable=False),
        sa.Column("messaging_rules_notes", sa.Text(), nullable=True),
        sa.Column("production_domain", sa.Text(), nullable=True),
        sa.Column("ownership", sa.JSON(), nullable=False),
        sa.Column("final_flow_notes", sa.Text(), nullable=True),
        sa.Column("general_notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_integration_intake_submissions")),
    )
    op.create_index(
        op.f("ix_integration_intake_submissions_project_key"),
        "integration_intake_submissions",
        ["project_key"],
        unique=False,
    )
    op.create_index(
        op.f("ix_integration_intake_submissions_status"),
        "integration_intake_submissions",
        ["status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_integration_intake_submissions_status"), table_name="integration_intake_submissions")
    op.drop_index(op.f("ix_integration_intake_submissions_project_key"), table_name="integration_intake_submissions")
    op.drop_table("integration_intake_submissions")
