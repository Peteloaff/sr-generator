"""Singer: an independently modeled, individually authorized voice identity.

Blueprint rule: never combine singers into one inseparable model, and never
train or render without the required consent flags.
"""

from __future__ import annotations

from sqlalchemy import JSON, Boolean, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from sr.models.base import Base, Timestamps, UUIDPrimaryKey


class Singer(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "singers"
    __table_args__ = (UniqueConstraint("band_id", "name", name="uq_singer_band_name"),)

    band_id: Mapped[str] = mapped_column(
        ForeignKey("bands.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(120))
    display_name: Mapped[str | None] = mapped_column(String(120), default=None)
    notes: Mapped[str | None] = mapped_column(Text, default=None)

    # Voice model wiring. The provider owns interpretation of the profile / path;
    # for local-dsp the profile is a small dict (pitch/formant/brightness/...),
    # for a neural provider ``voice_model_path_or_id`` points at weights.
    voice_model_provider: Mapped[str | None] = mapped_column(String(60), default=None)
    voice_model_path_or_id: Mapped[str | None] = mapped_column(String(500), default=None)
    voice_profile_json: Mapped[dict | None] = mapped_column(JSON, default=None)

    clean_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    scream_enabled: Mapped[bool] = mapped_column(Boolean, default=False)

    training_status: Mapped[str] = mapped_column(String(20), default="none")
    training_samples: Mapped[int] = mapped_column(Integer, default=0)

    # Consent / governance - enforced before training or rendering.
    consent_training: Mapped[bool] = mapped_column(Boolean, default=False)
    consent_generation: Mapped[bool] = mapped_column(Boolean, default=False)
    consent_commercial: Mapped[bool] = mapped_column(Boolean, default=False)
    consent_version: Mapped[str | None] = mapped_column(String(60), default=None)
    consent_source_ref: Mapped[str | None] = mapped_column(String(500), default=None)

    band: Mapped[Band] = relationship(back_populates="singers")  # noqa: F821
    assignments: Mapped[list[VocalAssignment]] = relationship(  # noqa: F821
        back_populates="singer", cascade="all, delete-orphan"
    )
