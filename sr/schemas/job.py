from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from sr.models.enums import JobType


class JobCreate(BaseModel):
    job_type: JobType = JobType.MOCK_GENERATION
    song_id: str | None = None
    section_id: str | None = None
    seed: int | None = None
    parameters: dict[str, Any] = Field(default_factory=dict)
    input_asset_ids: list[str] = Field(default_factory=list)


class AssetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    asset_type: str
    file_path: str
    duration: float | None
    sample_rate: int | None
    channels: int | None
    version: int
    parent_asset_id: str | None
    generation_job_id: str | None


class JobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    job_type: str
    provider: str
    provider_version: str | None
    status: str
    progress: float
    seed: int | None
    song_id: str | None
    section_id: str | None
    parameters_json: dict[str, Any] | None
    input_asset_ids: list[str] | None
    logs: str | None
    error: str | None
    attempts: int
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    outputs: list[AssetRead] = []
