"""stage 13: audio_assets.player_id for player samples + separated stems

Revision ID: b2f1a6d34c07
Revises: a1c7f4e02b19
Create Date: 2026-09-07 13:30:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "b2f1a6d34c07"
down_revision: str | None = "a1c7f4e02b19"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("audio_assets", schema=None) as batch_op:
        batch_op.add_column(sa.Column("player_id", sa.String(length=36), nullable=True))
        batch_op.create_index(
            batch_op.f("ix_audio_assets_player_id"), ["player_id"], unique=False
        )
        batch_op.create_foreign_key(
            "fk_audio_assets_player_id", "players", ["player_id"], ["id"], ondelete="SET NULL"
        )


def downgrade() -> None:
    with op.batch_alter_table("audio_assets", schema=None) as batch_op:
        batch_op.drop_constraint("fk_audio_assets_player_id", type_="foreignkey")
        batch_op.drop_index(batch_op.f("ix_audio_assets_player_id"))
        batch_op.drop_column("player_id")
