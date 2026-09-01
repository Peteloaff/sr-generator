"""SectionRevision: the edit history of one section's arrangement + render.

Stage 9 (surgical regeneration) writes one row every time a section or a single
role is regenerated, snapshotting the vocal-role configuration and pointing at the
render job that produced the audio. ``is_current`` marks the live revision;
rollback restores an earlier snapshot.
"""

from __future__ import annotations

from sqlalchemy import JSON, Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from sr.models.base import Base, Timestamps, UUIDPrimaryKey


class SectionRevision(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "section_revisions"

    section_id: Mapped[str] = mapped_column(
        ForeignKey("song_sections.id", ondelete="CASCADE"), index=True
    )
    revision: Mapped[int] = mapped_column(Integer, default=1)
    kind: Mapped[str] = mapped_column(String(20), default="full")  # full|role|swap|rollback
    roles_snapshot_json: Mapped[list | None] = mapped_column(JSON, default=None)
    render_job_id: Mapped[str | None] = mapped_column(
        ForeignKey("generation_jobs.id", ondelete="SET NULL"), default=None
    )
    changed_role_id: Mapped[str | None] = mapped_column(String(36), default=None)
    note: Mapped[str | None] = mapped_column(Text, default=None)
    is_current: Mapped[bool] = mapped_column(Boolean, default=True)
