"""BandAdapter: a trained conditioning descriptor for band-specific generation.

For the local synth provider it is a small character vector + tempo/key priors
distilled from the Band DNA. For a neural provider it would point at LoRA
weights. Either way it is provider-owned and carries the ``dataset_version`` it
was trained from, so a generation is traceable to a dataset.
"""

from __future__ import annotations

from sqlalchemy import JSON, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from sr.models.base import Base, Timestamps, UUIDPrimaryKey


class BandAdapter(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "band_adapters"
    __table_args__ = (UniqueConstraint("band_id", "name", name="uq_band_adapter_name"),)

    band_id: Mapped[str] = mapped_column(
        ForeignKey("bands.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(120))
    provider: Mapped[str] = mapped_column(String(60))
    provider_version: Mapped[str] = mapped_column(String(60))
    dataset_version: Mapped[str | None] = mapped_column(String(32), default=None)
    spec_json: Mapped[dict] = mapped_column(JSON)
    is_active: Mapped[bool] = mapped_column(default=True)
