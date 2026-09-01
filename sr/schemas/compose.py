from __future__ import annotations

from pydantic import BaseModel, Field


class FullSongRequest(BaseModel):
    prompt: str | None = Field(default=None, max_length=2000)
    lyrics: str | None = None
    seed: int | None = None
    adapter_id: str | None = None
    section_seconds: float | None = Field(default=None, gt=1, le=60)
    structure: list[str] | None = None
    replace: bool = True


class RegenerateSectionRequest(BaseModel):
    seed: int | None = None
    note: str | None = Field(default=None, max_length=200)


class RegenerateRoleRequest(BaseModel):
    seed: int | None = None
    # optional single-role singer swap, keeping every other performance identical
    swap_from_singer_id: str | None = None
    swap_to_singer_id: str | None = None
    note: str | None = Field(default=None, max_length=200)


class RollbackRequest(BaseModel):
    revision: int


class ArrangementApplyRequest(BaseModel):
    section_ids: list[str] | None = None
    overwrite: bool = False
    seed: int | None = None


class MorphCreate(BaseModel):
    section_id: str
    from_singer_id: str
    to_singer_id: str
    curve: str = Field(default="equal_power", pattern="^(linear|equal_power|scurve)$")
    start_frac: float = Field(default=0.2, ge=0.0, le=1.0)
    end_frac: float = Field(default=0.8, ge=0.0, le=1.0)
