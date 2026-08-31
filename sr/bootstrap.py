"""First-run bootstrap: guarantee a default Band exists.

Called on API startup and from tests. The product is single-band by default, but
every row is scoped to a band so a second band is just another row.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from sr.models.band import DEFAULT_BAND_SLUG, Band


def ensure_default_band(db: Session) -> Band:
    band = db.scalar(select(Band).where(Band.slug == DEFAULT_BAND_SLUG))
    if band is None:
        band = Band(name="My Band", slug=DEFAULT_BAND_SLUG)
        db.add(band)
        db.commit()
        db.refresh(band)
    return band


def default_band_id(db: Session) -> str:
    return ensure_default_band(db).id
