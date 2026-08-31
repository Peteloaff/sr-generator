"""AudioAsset: every audio artifact, versioned, with lineage.

``parent_asset_id`` + ``generation_job_id`` mean every output knows which source
assets and which job produced it. Stems are first-class - never collapse to a
master-only artifact.
"""

from __future__ import annotations

from sqlalchemy import Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from sr.models.base import Base, Timestamps, UUIDPrimaryKey


class AudioAsset(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "audio_assets"

    song_id: Mapped[str | None] = mapped_column(
        ForeignKey("songs.id", ondelete="CASCADE"), default=None, index=True
    )
    section_id: Mapped[str | None] = mapped_column(
        ForeignKey("song_sections.id", ondelete="SET NULL"), default=None, index=True
    )
    singer_id: Mapped[str | None] = mapped_column(
        ForeignKey("singers.id", ondelete="SET NULL"), default=None, index=True
    )
    generation_job_id: Mapped[str | None] = mapped_column(
        ForeignKey("generation_jobs.id", ondelete="SET NULL"), default=None, index=True
    )
    parent_asset_id: Mapped[str | None] = mapped_column(
        ForeignKey("audio_assets.id", ondelete="SET NULL"), default=None, index=True
    )

    asset_type: Mapped[str] = mapped_column(String(40), index=True)
    label: Mapped[str | None] = mapped_column(String(200), default=None)
    file_path: Mapped[str] = mapped_column(String(500))
    sample_rate: Mapped[int | None] = mapped_column(Integer, default=None)
    channels: Mapped[int | None] = mapped_column(Integer, default=None)
    duration: Mapped[float | None] = mapped_column(Float, default=None)
    version: Mapped[int] = mapped_column(Integer, default=1)

    generation_job: Mapped[GenerationJob | None] = relationship(  # noqa: F821
        back_populates="outputs"
    )
    children: Mapped[list[AudioAsset]] = relationship()
