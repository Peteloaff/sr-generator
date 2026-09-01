"""RenderTake: one virtual performance produced by the layering engine.

Every take stores its child seed and the *exact* micro-variation values that were
applied (timing, pitch, formant, gain, pan), plus the source and output assets.
This is what makes "same inputs + provider version + seed -> identical mix" true:
a render can be reconstructed take-for-take from these rows.
"""

from __future__ import annotations

from sqlalchemy import BigInteger, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from sr.models.base import Base, Timestamps, UUIDPrimaryKey


class RenderTake(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "render_takes"

    generation_job_id: Mapped[str] = mapped_column(
        ForeignKey("generation_jobs.id", ondelete="CASCADE"), index=True
    )
    vocal_role_id: Mapped[str] = mapped_column(
        ForeignKey("vocal_roles.id", ondelete="CASCADE"), index=True
    )
    singer_id: Mapped[str] = mapped_column(
        ForeignKey("singers.id", ondelete="CASCADE"), index=True
    )
    take_index: Mapped[int] = mapped_column(Integer)
    child_seed: Mapped[int] = mapped_column(BigInteger)

    # Applied values = per-assignment fixed offset + bounded humanization jitter.
    timing_offset_ms: Mapped[float] = mapped_column(Float, default=0.0)
    pitch_cents: Mapped[float] = mapped_column(Float, default=0.0)
    formant_shift: Mapped[float] = mapped_column(Float, default=0.0)
    gain_db: Mapped[float] = mapped_column(Float, default=0.0)
    pan: Mapped[float] = mapped_column(Float, default=0.0)

    source_kind: Mapped[str] = mapped_column(String(20), default="mock")  # "upload" | "mock"
    source_asset_id: Mapped[str | None] = mapped_column(
        ForeignKey("audio_assets.id", ondelete="SET NULL"), default=None
    )
    output_asset_id: Mapped[str | None] = mapped_column(
        ForeignKey("audio_assets.id", ondelete="SET NULL"), default=None
    )

    generation_job: Mapped[GenerationJob] = relationship()  # noqa: F821
