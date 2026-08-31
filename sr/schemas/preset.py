from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from sr.schemas.vocal import VocalRoleRead


class PresetCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = None
    from_section_id: str | None = None  # capture the section's current roles
    spec: dict[str, Any] | None = None  # or provide the spec directly


class PresetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    band_id: str
    name: str
    description: str | None
    spec_json: dict[str, Any]
    created_at: datetime


class ApplyRequest(BaseModel):
    section_id: str


class ApplyResult(BaseModel):
    section_id: str
    created_roles: list[VocalRoleRead]
    skipped_singers: list[str]
