"""widen seed columns to BIGINT

The deterministic seed derivation (sr/common/seeds.py) produces 63-bit values.
SQLite's INTEGER is 64-bit so this was invisible in dev/tests, but Postgres
INTEGER is 32-bit and overflows. All seed-bearing columns become BIGINT.

Revision ID: 5c3232296ddf
Revises: 82b9f0a42441
Create Date: 2026-09-01 21:45:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "5c3232296ddf"
down_revision: str | None = "82b9f0a42441"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_COLS = [
    ("songs", "seed"),
    ("song_sections", "generation_seed"),
    ("generation_jobs", "seed"),
    ("render_takes", "child_seed"),
    ("vocal_assignments", "seed"),
]


def upgrade() -> None:
    for table, col in _COLS:
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.alter_column(col, type_=sa.BigInteger(), existing_type=sa.Integer())


def downgrade() -> None:
    for table, col in _COLS:
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.alter_column(col, type_=sa.Integer(), existing_type=sa.BigInteger())
