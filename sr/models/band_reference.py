"""BandReference: an uploaded catalogue song used for analysis and, once
explicitly approved, as training/conditioning data (Band DNA - Stage 6)."""

from __future__ import annotations

from sqlalchemy import JSON, Boolean, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from sr.models.base import Base, Timestamps, UUIDPrimaryKey


class BandReference(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "band_references"

    band_id: Mapped[str] = mapped_column(
        ForeignKey("bands.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(200))
    source_file: Mapped[str | None] = mapped_column(String(500), default=None)
    bpm: Mapped[float | None] = mapped_column(Float, default=None)
    key: Mapped[str | None] = mapped_column(String(20), default=None)
    tuning: Mapped[str | None] = mapped_column(String(40), default=None)
    tags: Mapped[list | None] = mapped_column(JSON, default=None)
    structure_json: Mapped[dict | None] = mapped_column(JSON, default=None)
    analysis_json: Mapped[dict | None] = mapped_column(JSON, default=None)
    notes: Mapped[str | None] = mapped_column(Text, default=None)

    # Never assume an upload is training data.
    approved_for_training: Mapped[bool] = mapped_column(Boolean, default=False)

    band: Mapped[Band] = relationship(back_populates="references")  # noqa: F821
