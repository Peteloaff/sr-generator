"""VocalPreset: a saved, reusable vocal-stack recipe.

Blueprint section 13: save combinations like "Brian Big Chorus", "Pete Verse",
"All-Band Shout". A preset captures one or more vocal roles - role type, ensemble
size, width, humanization, processing chain, and singers *by name* + weight +
interval - so it can be applied to any section of any band.
"""

from __future__ import annotations

from sqlalchemy import JSON, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from sr.models.base import Base, Timestamps, UUIDPrimaryKey


class VocalPreset(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "vocal_presets"
    __table_args__ = (UniqueConstraint("band_id", "name", name="uq_vocal_preset_band_name"),)

    band_id: Mapped[str] = mapped_column(
        ForeignKey("bands.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str | None] = mapped_column(Text, default=None)
    # {"roles": [{role_type, ensemble_size, width, humanize_*, processing,
    #             "assignments": [{singer, weight_percent, interval_semitones, gain_db, pan}]}]}
    spec_json: Mapped[dict] = mapped_column(JSON)
