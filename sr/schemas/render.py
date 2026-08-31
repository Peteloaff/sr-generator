from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class RenderRequest(BaseModel):
    seed: int | None = None
    duration: float | None = Field(default=None, gt=0, le=600)
    # "ensemble" = full production; "flat" = naive same-take stack (the A/B baseline)
    mode: Literal["ensemble", "flat"] = "ensemble"


class ABResult(BaseModel):
    seed: int
    ensemble_job_id: str
    flat_job_id: str
    ensemble: dict
    flat: dict
    verdict: dict


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
