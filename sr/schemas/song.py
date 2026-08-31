from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from sr.models.enums import SectionType, SongStatus


class SongCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    project_id: str | None = None
    bpm: float | None = None
    key: str | None = None
    time_signature: str | None = "4/4"
    prompt: str | None = None
    lyrics: str | None = None
    seed: int | None = None


class SongUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    project_id: str | None = None
    bpm: float | None = None
    key: str | None = None
    time_signature: str | None = None
    duration: float | None = None
    prompt: str | None = None
    lyrics: str | None = None
    status: SongStatus | None = None
    seed: int | None = None
    reference_profile_id: str | None = None


class SongRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str | None
    title: str
    bpm: float | None
    key: str | None
    time_signature: str | None
    duration: float | None
    prompt: str | None
    lyrics: str | None
    status: str
    seed: int | None
    reference_profile_id: str | None
    created_at: datetime
    updated_at: datetime


class SectionCreate(BaseModel):
    section_type: SectionType = SectionType.OTHER
    name: str | None = None
    start_time: float | None = None
    end_time: float | None = None
    order_index: int = 0
    lyrics: str | None = None
    prompt_override: str | None = None
    generation_seed: int | None = None


class SectionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    song_id: str
    section_type: str
    name: str | None
    start_time: float | None
    end_time: float | None
    order_index: int
    lyrics: str | None
    prompt_override: str | None
    generation_seed: int | None


class LyricLineCreate(BaseModel):
    text: str = ""
    section_id: str | None = None
    order_index: int = 0
    start_time: float | None = None
    end_time: float | None = None


class LyricLineRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    song_id: str
    section_id: str | None
    order_index: int
    text: str
    start_time: float | None
    end_time: float | None
