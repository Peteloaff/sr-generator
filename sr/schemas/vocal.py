from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from sr.models.enums import VocalRoleType


class VocalAssignmentCreate(BaseModel):
    singer_id: str
    weight_percent: float = Field(default=100.0, ge=0)
    gain_db: float = 0.0
    pan: float = Field(default=0.0, ge=-100, le=100)
    pitch_offset_semitones: float = 0.0
    timing_offset_ms: float = 0.0
    formant_shift: float = 0.0
    style: str | None = None
    seed: int | None = None


class VocalAssignmentUpdate(BaseModel):
    weight_percent: float | None = Field(default=None, ge=0)
    gain_db: float | None = None
    pan: float | None = Field(default=None, ge=-100, le=100)
    pitch_offset_semitones: float | None = None
    timing_offset_ms: float | None = None
    formant_shift: float | None = None
    style: str | None = None
    seed: int | None = None


class VocalAssignmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    vocal_role_id: str
    singer_id: str
    weight_percent: float
    gain_db: float
    pan: float
    pitch_offset_semitones: float
    timing_offset_ms: float
    formant_shift: float
    style: str | None
    seed: int | None


class VocalRoleCreate(BaseModel):
    role_type: VocalRoleType
    ensemble_size: int = Field(default=1, ge=1, le=128)
    width: float = Field(default=0.0, ge=0, le=100)
    humanize_timing_ms: float = Field(default=0.0, ge=0)
    humanize_pitch_cents: float = Field(default=0.0, ge=0)
    humanize_formant: float = Field(default=0.0, ge=0)
    notes: str | None = None
    assignments: list[VocalAssignmentCreate] = Field(default_factory=list)


class VocalRoleUpdate(BaseModel):
    role_type: VocalRoleType | None = None
    ensemble_size: int | None = Field(default=None, ge=1, le=128)
    width: float | None = Field(default=None, ge=0, le=100)
    humanize_timing_ms: float | None = Field(default=None, ge=0)
    humanize_pitch_cents: float | None = Field(default=None, ge=0)
    humanize_formant: float | None = Field(default=None, ge=0)
    notes: str | None = None


class NormalizedShare(BaseModel):
    singer_id: str
    weight_percent: float
    normalized_percent: float
    ensemble_takes: int


class VocalRoleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    section_id: str | None
    lyric_line_id: str | None
    role_type: str
    ensemble_size: int
    width: float
    humanize_timing_ms: float
    humanize_pitch_cents: float
    humanize_formant: float
    notes: str | None
    assignments: list[VocalAssignmentRead] = []
