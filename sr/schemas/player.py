from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from sr.models.enums import PlayerRole, TrainingStatus


class PlayerBase(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    role: PlayerRole
    display_name: str | None = None
    notes: str | None = None
    intensity: float | None = Field(default=None, ge=0.0, le=1.0)
    consent_training: bool = False
    consent_generation: bool = False
    consent_commercial: bool = False
    consent_version: str | None = None
    consent_source_ref: str | None = None


class PlayerCreate(PlayerBase):
    band_id: str | None = None  # defaults to the active band


class PlayerFromPreset(BaseModel):
    preset: str  # "<role>.<vibe>", e.g. "lead_guitar.metal"
    name: str = Field(min_length=1, max_length=120)
    band_id: str | None = None


class ApplyPresetRequest(BaseModel):
    preset: str


class PlayerUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    role: PlayerRole | None = None
    display_name: str | None = None
    notes: str | None = None
    intensity: float | None = Field(default=None, ge=0.0, le=1.0)
    training_status: TrainingStatus | None = None
    is_active: bool | None = None
    consent_training: bool | None = None
    consent_generation: bool | None = None
    consent_commercial: bool | None = None
    consent_version: str | None = None
    consent_source_ref: str | None = None


class PlayerRead(PlayerBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    band_id: str
    style_model_provider: str | None
    style_profile_json: dict | None
    training_status: str
    training_samples: int
    is_active: bool
    created_at: datetime
    updated_at: datetime
