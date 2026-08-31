"""GenerationJob: every long-running audio/ML operation is one of these.

Captures input asset versions, parameters, provider/model version, seed, status,
logs, and output assets - required for all jobs by the blueprint scope rules.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from sr.models.base import Base, Timestamps, UUIDPrimaryKey


class GenerationJob(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "generation_jobs"

    song_id: Mapped[str | None] = mapped_column(
        ForeignKey("songs.id", ondelete="CASCADE"), default=None, index=True
    )
    section_id: Mapped[str | None] = mapped_column(
        ForeignKey("song_sections.id", ondelete="SET NULL"), default=None, index=True
    )

    job_type: Mapped[str] = mapped_column(String(40), index=True)
    provider: Mapped[str] = mapped_column(String(60), default="mock")
    provider_version: Mapped[str | None] = mapped_column(String(60), default=None)
    status: Mapped[str] = mapped_column(String(20), default="queued", index=True)
    progress: Mapped[float] = mapped_column(Float, default=0.0)  # 0..1

    seed: Mapped[int | None] = mapped_column(Integer, default=None)
    parameters_json: Mapped[dict | None] = mapped_column(JSON, default=None)
    result_json: Mapped[dict | None] = mapped_column(JSON, default=None)
    input_asset_ids: Mapped[list | None] = mapped_column(JSON, default=None)
    logs: Mapped[str | None] = mapped_column(Text, default=None)
    error: Mapped[str | None] = mapped_column(Text, default=None)
    attempts: Mapped[int] = mapped_column(Integer, default=0)

    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)

    outputs: Mapped[list[AudioAsset]] = relationship(  # noqa: F821
        back_populates="generation_job"
    )

    def append_log(self, line: str) -> None:
        self.logs = (self.logs or "") + line.rstrip() + "\n"
