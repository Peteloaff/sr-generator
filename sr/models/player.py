"""Player: an AI instrumentalist band member, modeled from a real player's style.

The instrument-side analogue of :class:`sr.models.singer.Singer`. Upload songs a
player performed on, and ``train_player`` separates their instrument, learns the
style + tone (drive, brightness, timing feel, note density, ...), and stores it
as a reusable named profile you cast per section - "Dave, lead guitar".

Same governance as singers: never train or render without the consent flags.
"""

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

#: instrument roles a player can hold. lead vs rhythm guitar are distinct so the
#: cast can put a different player (and style) on each.
PLAYER_ROLES = ("lead_guitar", "rhythm_guitar", "bass", "drums", "keys")

#: which separated stem each role learns from / renders as
ROLE_STEM = {
    "lead_guitar": "guitar",
    "rhythm_guitar": "guitar",
    "bass": "bass",
    "drums": "drums",
    "keys": "keys",
}


class Player(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "players"
    __table_args__ = (UniqueConstraint("band_id", "name", name="uq_player_band_name"),)

    band_id: Mapped[str] = mapped_column(
        ForeignKey("bands.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(120))
    role: Mapped[str] = mapped_column(String(20))
    display_name: Mapped[str | None] = mapped_column(String(120), default=None)
    notes: Mapped[str | None] = mapped_column(Text, default=None)

    # Style model wiring - mirrors Singer's voice-model columns. For the local
    # provider ``style_profile_json`` is a small dict (drive/brightness/timing/
    # density/...); a neural provider points ``style_model_path_or_id`` at weights.
    style_model_provider: Mapped[str | None] = mapped_column(String(60), default=None)
    style_model_path_or_id: Mapped[str | None] = mapped_column(String(500), default=None)
    style_profile_json: Mapped[dict | None] = mapped_column(JSON, default=None)

    training_status: Mapped[str] = mapped_column(String(20), default="none")
    training_samples: Mapped[int] = mapped_column(Integer, default=0)

    # user-entered performance bias, applied on top of the learned profile
    intensity: Mapped[float | None] = mapped_column(Float, default=None)  # 0..1

    # Consent / governance - enforced before training or rendering.
    consent_training: Mapped[bool] = mapped_column(Boolean, default=False)
    consent_generation: Mapped[bool] = mapped_column(Boolean, default=False)
    consent_commercial: Mapped[bool] = mapped_column(Boolean, default=False)
    consent_version: Mapped[str | None] = mapped_column(String(60), default=None)
    consent_source_ref: Mapped[str | None] = mapped_column(String(500), default=None)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    band: Mapped[Band] = relationship(back_populates="players")  # noqa: F821
