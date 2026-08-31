"""Band: the top-level tenant. Singers, projects, and references belong to a band.

The product is "an AI version of one band", but nothing stops you running a
second band in the same install - each band's singers, catalogue, and projects
are fully isolated by ``band_id``.
"""

from __future__ import annotations

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from sr.models.base import Base, Timestamps, UUIDPrimaryKey

DEFAULT_BAND_SLUG = "default"


class Band(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "bands"

    name: Mapped[str] = mapped_column(String(200))
    slug: Mapped[str] = mapped_column(String(80), unique=True)
    notes: Mapped[str | None] = mapped_column(Text, default=None)

    singers: Mapped[list[Singer]] = relationship(  # noqa: F821
        back_populates="band", cascade="all, delete-orphan"
    )
    projects: Mapped[list[Project]] = relationship(  # noqa: F821
        back_populates="band", cascade="all, delete-orphan"
    )
    references: Mapped[list[BandReference]] = relationship(  # noqa: F821
        back_populates="band", cascade="all, delete-orphan"
    )
