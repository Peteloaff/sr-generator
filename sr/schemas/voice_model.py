from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class VoiceProfileUpdate(BaseModel):
    median_f0: float | None = Field(default=None, gt=0, le=2000)
    formant_semitones: float | None = Field(default=None, ge=-12, le=12)
    brightness: float | None = Field(default=None, ge=-1, le=1)
    breathiness: float | None = Field(default=None, ge=0, le=1)
    roughness: float | None = Field(default=None, ge=0, le=1)


class VoiceModelRead(BaseModel):
    singer_id: str
    training_status: str
    training_samples: int
    voice_model_provider: str | None
    voice_profile: dict[str, Any] | None
