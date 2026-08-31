from __future__ import annotations

import re
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class BandCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    slug: str | None = Field(default=None, max_length=80)
    notes: str | None = None

    @field_validator("slug")
    @classmethod
    def _slugify(cls, v: str | None) -> str | None:
        if v is None:
            return None
        s = re.sub(r"[^a-z0-9]+", "-", v.lower()).strip("-")
        if not s:
            raise ValueError("slug must contain a letter or digit")
        return s


class BandUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    notes: str | None = None


class BandRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    slug: str
    notes: str | None
    created_at: datetime
    updated_at: datetime
