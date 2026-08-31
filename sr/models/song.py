"""Song, SongSection, and LyricLine.

LyricLine is the SR Generator amendment to the blueprint data model: vocal roles
attach to a whole section *or* to a single lyric line (see sr/models/vocal.py and
sr/common/resolver.py for the inheritance rule).
"""

from __future__ import annotations

from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from sr.models.base import Base, Timestamps, UUIDPrimaryKey


class Song(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "songs"

    project_id: Mapped[str | None] = mapped_column(
        ForeignKey("projects.id", ondelete="SET NULL"), default=None, index=True
    )
    title: Mapped[str] = mapped_column(String(200))
    bpm: Mapped[float | None] = mapped_column(Float, default=None)
    key: Mapped[str | None] = mapped_column(String(20), default=None)
    time_signature: Mapped[str | None] = mapped_column(String(12), default="4/4")
    duration: Mapped[float | None] = mapped_column(Float, default=None)
    prompt: Mapped[str | None] = mapped_column(Text, default=None)
    lyrics: Mapped[str | None] = mapped_column(Text, default=None)
    status: Mapped[str] = mapped_column(String(20), default="draft")
    seed: Mapped[int | None] = mapped_column(Integer, default=None)
    reference_profile_id: Mapped[str | None] = mapped_column(
        ForeignKey("band_references.id", ondelete="SET NULL"), default=None
    )

    project: Mapped[Project | None] = relationship(back_populates="songs")  # noqa: F821
    sections: Mapped[list[SongSection]] = relationship(
        back_populates="song",
        cascade="all, delete-orphan",
        order_by="SongSection.order_index",
    )
    lyric_lines: Mapped[list[LyricLine]] = relationship(
        back_populates="song",
        cascade="all, delete-orphan",
        order_by="LyricLine.order_index",
    )


class SongSection(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "song_sections"

    song_id: Mapped[str] = mapped_column(
        ForeignKey("songs.id", ondelete="CASCADE"), index=True
    )
    section_type: Mapped[str] = mapped_column(String(20), default="other")
    name: Mapped[str | None] = mapped_column(String(120), default=None)
    start_time: Mapped[float | None] = mapped_column(Float, default=None)
    end_time: Mapped[float | None] = mapped_column(Float, default=None)
    order_index: Mapped[int] = mapped_column(Integer, default=0)
    lyrics: Mapped[str | None] = mapped_column(Text, default=None)
    prompt_override: Mapped[str | None] = mapped_column(Text, default=None)
    generation_seed: Mapped[int | None] = mapped_column(Integer, default=None)

    song: Mapped[Song] = relationship(back_populates="sections")
    lines: Mapped[list[LyricLine]] = relationship(
        back_populates="section", order_by="LyricLine.order_index"
    )
    vocal_roles: Mapped[list[VocalRole]] = relationship(  # noqa: F821
        back_populates="section",
        cascade="all, delete-orphan",
        primaryjoin="SongSection.id == VocalRole.section_id",
    )


class LyricLine(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "lyric_lines"

    song_id: Mapped[str] = mapped_column(
        ForeignKey("songs.id", ondelete="CASCADE"), index=True
    )
    section_id: Mapped[str | None] = mapped_column(
        ForeignKey("song_sections.id", ondelete="SET NULL"), default=None, index=True
    )
    order_index: Mapped[int] = mapped_column(Integer, default=0)
    text: Mapped[str] = mapped_column(Text, default="")
    start_time: Mapped[float | None] = mapped_column(Float, default=None)
    end_time: Mapped[float | None] = mapped_column(Float, default=None)

    song: Mapped[Song] = relationship(back_populates="lyric_lines")
    section: Mapped[SongSection | None] = relationship(back_populates="lines")
    vocal_roles: Mapped[list[VocalRole]] = relationship(  # noqa: F821
        back_populates="lyric_line",
        cascade="all, delete-orphan",
        primaryjoin="LyricLine.id == VocalRole.lyric_line_id",
    )
