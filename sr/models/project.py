"""Project: a container grouping related songs (an album, an EP, a session)."""

from __future__ import annotations

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from sr.models.base import Base, Timestamps, UUIDPrimaryKey


class Project(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "projects"

    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text, default=None)

    songs: Mapped[list[Song]] = relationship(  # noqa: F821
        back_populates="project", cascade="all, delete-orphan"
    )
