"""phase 1 handover marker

Revision ID: 20260511_0004
Revises: 20260429_0003
Create Date: 2026-05-11 00:04:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence


revision: str = "20260511_0004"
down_revision: str | None = "20260429_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
