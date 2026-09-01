"""stage 11: experimental vocal morph / timbre blend

Revision ID: 82b9f0a42441
Revises: 9d72dc10b54a
Create Date: 2026-09-01 09:40:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "82b9f0a42441"
down_revision: str | None = "9d72dc10b54a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "vocal_morphs",
        sa.Column("section_id", sa.String(length=36), nullable=False),
        sa.Column("from_singer_id", sa.String(length=36), nullable=False),
        sa.Column("to_singer_id", sa.String(length=36), nullable=False),
        sa.Column("curve", sa.String(length=20), nullable=False),
        sa.Column("start_frac", sa.Float(), nullable=False),
        sa.Column("end_frac", sa.Float(), nullable=False),
        sa.Column("quality_json", sa.JSON(), nullable=True),
        sa.Column("preview_asset_id", sa.String(length=36), nullable=True),
        sa.Column("committed", sa.Boolean(), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["section_id"], ["song_sections.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["from_singer_id"], ["singers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["to_singer_id"], ["singers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["preview_asset_id"], ["audio_assets.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("vocal_morphs", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_vocal_morphs_section_id"), ["section_id"], unique=False
        )


def downgrade() -> None:
    with op.batch_alter_table("vocal_morphs", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_vocal_morphs_section_id"))
    op.drop_table("vocal_morphs")
