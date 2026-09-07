"""InstrumentSlot: which player performs which instrument, per song or section.

A slot with ``section_id`` NULL is the whole-song default for that role; a slot
with a ``section_id`` overrides it for that one section. ``dials_json`` holds
small per-part deltas (busier/brighter/harder/push/swing, each -1..1) and
``explore`` (0 = faithful to the learned style, 1 = wander).
"""

from __future__ import annotations

from sqlalchemy import JSON, Boolean, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from sr.models.base import Base, Timestamps, UUIDPrimaryKey

DIAL_KEYS = ("busier", "brighter", "harder", "push", "swing")


class InstrumentSlot(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "instrument_slots"

    song_id: Mapped[str] = mapped_column(
        ForeignKey("songs.id", ondelete="CASCADE"), index=True
    )
    section_id: Mapped[str | None] = mapped_column(
        ForeignKey("song_sections.id", ondelete="CASCADE"), default=None, index=True
    )
    role: Mapped[str] = mapped_column(String(20))
    player_id: Mapped[str | None] = mapped_column(
        ForeignKey("players.id", ondelete="SET NULL"), default=None, index=True
    )
    muted: Mapped[bool] = mapped_column(Boolean, default=False)
    gain_db: Mapped[float] = mapped_column(Float, default=0.0)
    explore: Mapped[float] = mapped_column(Float, default=0.0)
    dials_json: Mapped[dict | None] = mapped_column(JSON, default=None)
