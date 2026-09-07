"""stage 15: instrument casting slots

Revision ID: d4b8f1907e63
Revises: c3a9e5b71d42
Create Date: 2026-09-07 16:30:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "d4b8f1907e63"
down_revision: str | None = "c3a9e5b71d42"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "instrument_slots",
        sa.Column("song_id", sa.String(length=36), nullable=False),
        sa.Column("section_id", sa.String(length=36), nullable=True),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("player_id", sa.String(length=36), nullable=True),
        sa.Column("muted", sa.Boolean(), nullable=False),
        sa.Column("gain_db", sa.Float(), nullable=False),
        sa.Column("explore", sa.Float(), nullable=False),
        sa.Column("dials_json", sa.JSON(), nullable=True),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["song_id"], ["songs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["section_id"], ["song_sections.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["player_id"], ["players.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("instrument_slots", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_instrument_slots_song_id"), ["song_id"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_instrument_slots_section_id"), ["section_id"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_instrument_slots_player_id"), ["player_id"], unique=False
        )


def downgrade() -> None:
    with op.batch_alter_table("instrument_slots", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_instrument_slots_player_id"))
        batch_op.drop_index(batch_op.f("ix_instrument_slots_section_id"))
        batch_op.drop_index(batch_op.f("ix_instrument_slots_song_id"))
    op.drop_table("instrument_slots")
