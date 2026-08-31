"""BandReference: an uploaded catalogue song used for analysis and, once
explicitly approved, as training/conditioning data (Band DNA - Stage 6)."""

from __future__ import annotations

from sqlalchemy import (
    JSON,
    Boolean,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from sr.models.base import Base, Timestamps, UUIDPrimaryKey


class BandReference(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "band_references"
    __table_args__ = (
        UniqueConstraint("band_id", "content_hash", name="uq_band_reference_content"),
    )

    band_id: Mapped[str] = mapped_column(
        ForeignKey("bands.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(200))
    source_file: Mapped[str | None] = mapped_column(String(500), default=None)
    source_kind: Mapped[str] = mapped_column(String(20), default="upload")  # upload | folder
    content_hash: Mapped[str | None] = mapped_column(String(32), default=None)

    duration: Mapped[float | None] = mapped_column(Float, default=None)
    sample_rate: Mapped[int | None] = mapped_column(Integer, default=None)
    channels: Mapped[int | None] = mapped_column(Integer, default=None)

    bpm: Mapped[float | None] = mapped_column(Float, default=None)
    key: Mapped[str | None] = mapped_column(String(20), default=None)
    tuning: Mapped[str | None] = mapped_column(String(40), default=None)
    tags: Mapped[list | None] = mapped_column(JSON, default=None)
    structure_json: Mapped[dict | None] = mapped_column(JSON, default=None)
    analysis_json: Mapped[dict | None] = mapped_column(JSON, default=None)
    quality_json: Mapped[dict | None] = mapped_column(JSON, default=None)
    notes: Mapped[str | None] = mapped_column(Text, default=None)

    analysis_status: Mapped[str] = mapped_column(String(20), default="none")
    analysis_provider: Mapped[str | None] = mapped_column(String(60), default=None)
    analysis_version: Mapped[str | None] = mapped_column(String(60), default=None)

    # Never assume an upload is training data.
    approved_for_training: Mapped[bool] = mapped_column(Boolean, default=False)

    band: Mapped[Band] = relationship(back_populates="references")  # noqa: F821
