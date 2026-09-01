"""Singer: an independently modeled, individually authorized voice identity.

Blueprint rule: never combine singers into one inseparable model, and never
train or render without the required consent flags.
"""

from __future__ import annotations

from sqlalchemy import JSON, Boolean, Float, ForeignKey, Integer, String, Text, UniqueConstraint
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

    # Stage 10 arranger metadata - user-entered, not measured. Range as MIDI note
    # numbers; preferred_roles a free list ("chorus_lead", "scream", "octave_double",
    # "high_harmony", "low_harmony", "verse_lead", "gang"); energy_fit low|mid|high.
    range_low_midi: Mapped[float | None] = mapped_column(Float, default=None)
    range_high_midi: Mapped[float | None] = mapped_column(Float, default=None)
    preferred_roles: Mapped[list | None] = mapped_column(JSON, default=None)
    energy_fit: Mapped[str | None] = mapped_column(String(10), default=None)
    arranger_json: Mapped[dict | None] = mapped_column(JSON, default=None)

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
