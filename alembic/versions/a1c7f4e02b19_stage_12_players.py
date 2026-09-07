"""stage 12: instrumentalist players roster

Revision ID: a1c7f4e02b19
Revises: 5c3232296ddf
Create Date: 2026-09-07 12:00:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "a1c7f4e02b19"
down_revision: str | None = "5c3232296ddf"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "players",
        sa.Column("band_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("display_name", sa.String(length=120), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("style_model_provider", sa.String(length=60), nullable=True),
        sa.Column("style_model_path_or_id", sa.String(length=500), nullable=True),
        sa.Column("style_profile_json", sa.JSON(), nullable=True),
        sa.Column("training_status", sa.String(length=20), nullable=False),
        sa.Column("training_samples", sa.Integer(), nullable=False),
        sa.Column("intensity", sa.Float(), nullable=True),
        sa.Column("consent_training", sa.Boolean(), nullable=False),
        sa.Column("consent_generation", sa.Boolean(), nullable=False),
        sa.Column("consent_commercial", sa.Boolean(), nullable=False),
        sa.Column("consent_version", sa.String(length=60), nullable=True),
        sa.Column("consent_source_ref", sa.String(length=500), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["band_id"], ["bands.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("band_id", "name", name="uq_player_band_name"),
    )
    with op.batch_alter_table("players", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_players_band_id"), ["band_id"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("players", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_players_band_id"))
    op.drop_table("players")
