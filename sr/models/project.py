"""Project: a container grouping related songs (an album, an EP, a session)."""

from __future__ import annotations

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from sr.models.base import Base, Timestamps, UUIDPrimaryKey


class Project(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "projects"

    band_id: Mapped[str] = mapped_column(
        ForeignKey("bands.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text, default=None)

    band: Mapped[Band] = relationship(back_populates="projects")  # noqa: F821
    songs: Mapped[list[Song]] = relationship(  # noqa: F821
        back_populates="project", cascade="all, delete-orphan"
    )
