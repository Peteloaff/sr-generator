from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from sr.models.enums import TrainingStatus


class ArrangerMeta(BaseModel):
    range_low_midi: float | None = Field(default=None, ge=24, le=96)
    range_high_midi: float | None = Field(default=None, ge=24, le=108)
    preferred_roles: list[str] | None = None
    energy_fit: str | None = Field(default=None, pattern="^(low|mid|high)$")
    arranger_json: dict | None = None


class SingerBase(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    display_name: str | None = None
    notes: str | None = None
    voice_model_provider: str | None = None
    voice_model_path_or_id: str | None = None
    clean_enabled: bool = True
    scream_enabled: bool = False
    consent_training: bool = False
    consent_generation: bool = False
    consent_commercial: bool = False
    consent_version: str | None = None
    consent_source_ref: str | None = None


class SingerCreate(SingerBase):
    band_id: str | None = None  # defaults to the active band


class SingerUpdate(ArrangerMeta):
    display_name: str | None = None
    notes: str | None = None
    voice_model_provider: str | None = None
    voice_model_path_or_id: str | None = None
    clean_enabled: bool | None = None
    scream_enabled: bool | None = None
    training_status: TrainingStatus | None = None
    consent_training: bool | None = None
    consent_generation: bool | None = None
    consent_commercial: bool | None = None
    consent_version: str | None = None
    consent_source_ref: str | None = None


class SingerRead(SingerBase, ArrangerMeta):
    model_config = ConfigDict(from_attributes=True)

    id: str
    band_id: str
    training_status: str
    training_samples: int
    created_at: datetime
    updated_at: datetime
