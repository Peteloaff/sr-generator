from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AudioAssetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    song_id: str | None
    section_id: str | None
    asset_type: str
    file_path: str
    sample_rate: int | None
    channels: int | None
    duration: float | None
    version: int
    parent_asset_id: str | None
    generation_job_id: str | None
    created_at: datetime


class WaveformRead(BaseModel):
    asset_id: str
    buckets: int
    duration: float | None
    peaks: list[list[float]]
