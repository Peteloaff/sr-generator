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
    """Resolve the active band from ?band_id=, the X-Band-Id header, or the default.

    An explicit ``?band_id=`` that does not exist is a 404. A stale ``X-Band-Id``
    header (e.g. a client that cached a deleted band) falls back to the default.
    """
    if band_id:
        band = db.get(Band, band_id)
        if band is None:
            raise HTTPException(404, f"band {band_id!r} not found")
        return band
    if x_band_id:
        band = db.get(Band, x_band_id)
        if band is not None:
            return band
    return ensure_default_band(db)
