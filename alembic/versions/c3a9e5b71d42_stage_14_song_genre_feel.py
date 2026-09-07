"""stage 14: genre / song feel on songs

Revision ID: c3a9e5b71d42
Revises: b2f1a6d34c07
Create Date: 2026-09-07 15:00:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c3a9e5b71d42"
down_revision: str | None = "b2f1a6d34c07"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("songs", schema=None) as batch_op:
        batch_op.add_column(sa.Column("genre", sa.String(length=40), nullable=True))
        batch_op.add_column(
            sa.Column("style_blend", sa.Float(), nullable=False, server_default="0.6")
        )


def downgrade() -> None:
    with op.batch_alter_table("songs", schema=None) as batch_op:
        batch_op.drop_column("style_blend")
        batch_op.drop_column("genre")
