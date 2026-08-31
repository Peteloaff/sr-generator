from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AdapterTrainRequest(BaseModel):
    name: str | None = Field(default=None, max_length=120)


class AdapterRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    band_id: str
    name: str
    provider: str
    provider_version: str
    dataset_version: str | None
    spec_json: dict[str, Any]
    is_active: bool
    created_at: datetime


class GenerateInstrumentalRequest(BaseModel):
    prompt: str = "band instrumental"
    seed: int | None = None
    adapter_id: str | None = None
    bpm: float | None = Field(default=None, gt=40, le=220)
    key: str | None = None
    duration: float | None = Field(default=None, gt=0, le=300)
