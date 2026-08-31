"""VocalRole and VocalAssignment - the heart of the Vocal Director.

A VocalRole (lead / double / harmony / background / gang / scream) attaches to
exactly one parent: a SongSection (the default) or a single LyricLine (an
override). A VocalRole holds one or more VocalAssignments, each pinning a singer
with a weight percent (allocation, NOT gain) plus separate mix/performance
controls.
"""

from __future__ import annotations

from sqlalchemy import CheckConstraint, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from sr.models.base import Base, Timestamps, UUIDPrimaryKey


class VocalRole(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "vocal_roles"
    __table_args__ = (
        CheckConstraint(
            "(section_id IS NOT NULL) <> (lyric_line_id IS NOT NULL)",
            name="ck_vocal_role_exactly_one_parent",
        ),
    )

    section_id: Mapped[str | None] = mapped_column(
        ForeignKey("song_sections.id", ondelete="CASCADE"), default=None, index=True
    )
    lyric_line_id: Mapped[str | None] = mapped_column(
        ForeignKey("lyric_lines.id", ondelete="CASCADE"), default=None, index=True
    )

    role_type: Mapped[str] = mapped_column(String(20))
    ensemble_size: Mapped[int] = mapped_column(Integer, default=1)
    width: Mapped[float] = mapped_column(Float, default=0.0)  # stereo width 0..100
    humanize_timing_ms: Mapped[float] = mapped_column(Float, default=0.0)
    humanize_pitch_cents: Mapped[float] = mapped_column(Float, default=0.0)
    humanize_formant: Mapped[float] = mapped_column(Float, default=0.0)
    notes: Mapped[str | None] = mapped_column(Text, default=None)

    section: Mapped[SongSection | None] = relationship(  # noqa: F821
        back_populates="vocal_roles",
        primaryjoin="SongSection.id == VocalRole.section_id",
    )
    lyric_line: Mapped[LyricLine | None] = relationship(  # noqa: F821
        back_populates="vocal_roles",
        primaryjoin="LyricLine.id == VocalRole.lyric_line_id",
    )
    assignments: Mapped[list[VocalAssignment]] = relationship(
        back_populates="vocal_role",
        cascade="all, delete-orphan",
    )


class VocalAssignment(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "vocal_assignments"

    vocal_role_id: Mapped[str] = mapped_column(
        ForeignKey("vocal_roles.id", ondelete="CASCADE"), index=True
    )
    singer_id: Mapped[str] = mapped_column(
        ForeignKey("singers.id", ondelete="CASCADE"), index=True
    )

    weight_percent: Mapped[float] = mapped_column(Float, default=100.0)  # allocation, not gain
    gain_db: Mapped[float] = mapped_column(Float, default=0.0)
    pan: Mapped[float] = mapped_column(Float, default=0.0)  # -100..100
    pitch_offset_semitones: Mapped[float] = mapped_column(Float, default=0.0)
    timing_offset_ms: Mapped[float] = mapped_column(Float, default=0.0)
    formant_shift: Mapped[float] = mapped_column(Float, default=0.0)
    style: Mapped[str | None] = mapped_column(String(40), default=None)
    seed: Mapped[int | None] = mapped_column(Integer, default=None)

    vocal_role: Mapped[VocalRole] = relationship(back_populates="assignments")
    singer: Mapped[Singer] = relationship(back_populates="assignments")  # noqa: F821
