"""stage 10: intelligent vocal arranger - singer preference/range metadata

Revision ID: 9d72dc10b54a
Revises: 8c448bb1aabc
Create Date: 2026-09-01 09:35:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "9d72dc10b54a"
down_revision: str | None = "8c448bb1aabc"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("singers", schema=None) as batch_op:
        batch_op.add_column(sa.Column("range_low_midi", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("range_high_midi", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("preferred_roles", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("energy_fit", sa.String(length=10), nullable=True))
        batch_op.add_column(sa.Column("arranger_json", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("singers", schema=None) as batch_op:
        batch_op.drop_column("arranger_json")
        batch_op.drop_column("energy_fit")
        batch_op.drop_column("preferred_roles")
        batch_op.drop_column("range_high_midi")
        batch_op.drop_column("range_low_midi")
