"""stage 9: surgical regeneration - section lock + revision history

Revision ID: 8c448bb1aabc
Revises: 877aea557911
Create Date: 2026-09-01 09:30:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "8c448bb1aabc"
down_revision: str | None = "877aea557911"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("song_sections", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "locked", sa.Boolean(), nullable=False, server_default=sa.false()
            )
        )

    op.create_table(
        "section_revisions",
        sa.Column("section_id", sa.String(length=36), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("roles_snapshot_json", sa.JSON(), nullable=True),
        sa.Column("render_job_id", sa.String(length=36), nullable=True),
        sa.Column("changed_role_id", sa.String(length=36), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("is_current", sa.Boolean(), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["section_id"], ["song_sections.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["render_job_id"], ["generation_jobs.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("section_revisions", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_section_revisions_section_id"), ["section_id"], unique=False
        )


def downgrade() -> None:
    with op.batch_alter_table("section_revisions", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_section_revisions_section_id"))
    op.drop_table("section_revisions")
    with op.batch_alter_table("song_sections", schema=None) as batch_op:
        batch_op.drop_column("locked")
