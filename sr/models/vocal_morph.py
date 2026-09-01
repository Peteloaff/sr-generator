"""VocalMorph: an automated transition from one singer identity to another across
a section (Stage 11, experimental).

Gated behind ``SR_EXPERIMENTAL_MORPH``. A morph renders a *preview* only - a
time-varying crossfade between the two singers' section vocals - with quality
flags. It is not wired into a section mix unless the preview passes and the user
explicitly commits it.
"""

from __future__ import annotations

from sqlalchemy import JSON, Boolean, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from sr.models.base import Base, Timestamps, UUIDPrimaryKey


class VocalMorph(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "vocal_morphs"

    section_id: Mapped[str] = mapped_column(
        ForeignKey("song_sections.id", ondelete="CASCADE"), index=True
    )
    from_singer_id: Mapped[str] = mapped_column(
        ForeignKey("singers.id", ondelete="CASCADE")
    )
    to_singer_id: Mapped[str] = mapped_column(
        ForeignKey("singers.id", ondelete="CASCADE")
    )
    curve: Mapped[str] = mapped_column(String(20), default="equal_power")
    start_frac: Mapped[float] = mapped_column(Float, default=0.2)
    end_frac: Mapped[float] = mapped_column(Float, default=0.8)

    quality_json: Mapped[dict | None] = mapped_column(JSON, default=None)
    preview_asset_id: Mapped[str | None] = mapped_column(
        ForeignKey("audio_assets.id", ondelete="SET NULL"), default=None
    )
    committed: Mapped[bool] = mapped_column(Boolean, default=False)
