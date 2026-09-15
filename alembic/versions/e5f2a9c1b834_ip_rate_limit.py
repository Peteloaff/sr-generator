"""per-IP daily generation rate limit (stopgap before accounts/login)

Revision ID: e5f2a9c1b834
Revises: d4b8f1907e63
Create Date: 2026-09-15 01:40:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "e5f2a9c1b834"
down_revision: str | None = "d4b8f1907e63"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ip_usage",
        sa.Column("ip", sa.String(length=64), nullable=False),
        sa.Column("day", sa.String(length=10), nullable=False),
        sa.Column("kind", sa.String(length=30), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("ip", "day", "kind", name="uq_ip_usage_ip_day_kind"),
    )
    with op.batch_alter_table("ip_usage", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_ip_usage_ip"), ["ip"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("ip_usage", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_ip_usage_ip"))
    op.drop_table("ip_usage")
