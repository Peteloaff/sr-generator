from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ReferenceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    band_id: str
    title: str
    source_file: str | None
    source_kind: str
    content_hash: str | None
    duration: float | None
    sample_rate: int | None
    channels: int | None
    bpm: float | None
    key: str | None
    tuning: str | None
    tags: list[str] | None
    structure_json: dict[str, Any] | None
    quality_json: dict[str, Any] | None
    notes: str | None
    analysis_status: str
    analysis_provider: str | None
    analysis_version: str | None
    approved_for_training: bool
    created_at: datetime


class ReferenceDetail(ReferenceRead):
    analysis_json: dict[str, Any] | None


class ReferenceUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    tags: list[str] | None = None
    notes: str | None = None
    bpm: float | None = Field(default=None, gt=0, le=400)
    key: str | None = None
    tuning: str | None = None
    approved_for_training: bool | None = None


class FolderImportRequest(BaseModel):
    path: str
    recursive: bool = True
    auto_approve: bool = False


class ManifestSnapshot(BaseModel):
    dataset_version: str
    snapshot_version: int
    path: str
    count: int
