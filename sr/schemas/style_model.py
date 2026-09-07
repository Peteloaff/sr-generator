from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class StyleProfileUpdate(BaseModel):
    """Manual tuning of a player's learned style (all optional)."""

    register_hz: float | None = Field(default=None, gt=20, le=12000)
    brightness: float | None = Field(default=None, ge=-1, le=1)
    drive: float | None = Field(default=None, ge=0, le=1)
    attack: float | None = Field(default=None, ge=0, le=1)
    sustain: float | None = Field(default=None, ge=0, le=1)
    note_density: float | None = Field(default=None, ge=0, le=20)
    busyness: float | None = Field(default=None, ge=0, le=1)
    dynamics: float | None = Field(default=None, ge=0, le=1)
    syncopation: float | None = Field(default=None, ge=0, le=1)
    swing: float | None = Field(default=None, ge=0, le=1)
    low_end: float | None = Field(default=None, ge=0, le=1)
    stereo_width: float | None = Field(default=None, ge=0, le=1)


class StyleModelRead(BaseModel):
    player_id: str
    role: str
    training_status: str
    training_samples: int
    style_model_provider: str | None
    style_profile: dict[str, Any] | None
