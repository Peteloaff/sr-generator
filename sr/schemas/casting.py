from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from sr.models.enums import PlayerRole


class DialSet(BaseModel):
    busier: float | None = Field(default=None, ge=-1, le=1)
    brighter: float | None = Field(default=None, ge=-1, le=1)
    harder: float | None = Field(default=None, ge=-1, le=1)
    push: float | None = Field(default=None, ge=-1, le=1)
    swing: float | None = Field(default=None, ge=-1, le=1)


class InstrumentSlotWrite(BaseModel):
    role: PlayerRole
    section_id: str | None = None  # None = whole-song default
    player_id: str | None = None
    muted: bool = False
    gain_db: float = Field(default=0.0, ge=-24, le=12)
    explore: float = Field(default=0.0, ge=0.0, le=1.0)
    dials: DialSet | None = None


class InstrumentSlotRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    song_id: str
    section_id: str | None
    role: str
    player_id: str | None
    muted: bool
    gain_db: float
    explore: float
    dials_json: dict | None
    created_at: datetime
    updated_at: datetime
