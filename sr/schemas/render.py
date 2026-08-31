from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class RenderRequest(BaseModel):
    seed: int | None = None
    duration: float | None = Field(default=None, gt=0, le=600)


class RenderTakeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    vocal_role_id: str
    singer_id: str
    take_index: int
    child_seed: int
    timing_offset_ms: float
    pitch_cents: float
    formant_shift: float
    gain_db: float
    pan: float
    source_kind: str
    source_asset_id: str | None
    output_asset_id: str | None
