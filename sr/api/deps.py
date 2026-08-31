"""Shared FastAPI dependencies."""

from __future__ import annotations

from fastapi import Depends, Header, HTTPException, Query
from sqlalchemy.orm import Session

from sr.bootstrap import ensure_default_band
from sr.db import get_db
from sr.models.band import Band


def get_band(
    band_id: str | None = Query(default=None),
    x_band_id: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> Band:
    """Resolve the active band from ?band_id=, the X-Band-Id header, or the default."""
    wanted = band_id or x_band_id
    if wanted:
        band = db.get(Band, wanted)
        if band is None:
            raise HTTPException(404, f"band {wanted!r} not found")
        return band
    return ensure_default_band(db)
