from __future__ import annotations

import re

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from sr.bootstrap import ensure_default_band
from sr.db import get_db
from sr.models.band import Band
from sr.models.project import Project
from sr.models.singer import Singer
from sr.schemas.band import BandCreate, BandRead, BandUpdate

router = APIRouter(prefix="/bands", tags=["bands"])


def _unique_slug(db: Session, base: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", base.lower()).strip("-") or "band"
    slug, n = base, 2
    while db.scalar(select(Band).where(Band.slug == slug)):
        slug, n = f"{base}-{n}", n + 1
    return slug


@router.get("", response_model=list[BandRead])
def list_bands(db: Session = Depends(get_db)) -> list[Band]:
    ensure_default_band(db)
    return list(db.scalars(select(Band).order_by(Band.created_at)))


@router.post("", response_model=BandRead, status_code=201)
def create_band(payload: BandCreate, db: Session = Depends(get_db)) -> Band:
    band = Band(
        name=payload.name,
        slug=_unique_slug(db, payload.slug or payload.name),
        notes=payload.notes,
    )
    db.add(band)
    db.commit()
    db.refresh(band)
    return band


@router.get("/{band_id}", response_model=BandRead)
def get_band(band_id: str, db: Session = Depends(get_db)) -> Band:
    band = db.get(Band, band_id)
    if band is None:
        raise HTTPException(404, "band not found")
    return band


@router.get("/{band_id}/stats")
def band_stats(band_id: str, db: Session = Depends(get_db)) -> dict:
    if db.get(Band, band_id) is None:
        raise HTTPException(404, "band not found")
    singers = db.scalar(select(func.count()).select_from(Singer).where(Singer.band_id == band_id))
    projects = db.scalar(
        select(func.count()).select_from(Project).where(Project.band_id == band_id)
    )
    return {"band_id": band_id, "singers": singers, "projects": projects}


@router.patch("/{band_id}", response_model=BandRead)
def update_band(band_id: str, payload: BandUpdate, db: Session = Depends(get_db)) -> Band:
    band = db.get(Band, band_id)
    if band is None:
        raise HTTPException(404, "band not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(band, field, value)
    db.commit()
    db.refresh(band)
    return band


@router.delete("/{band_id}", status_code=204)
def delete_band(band_id: str, db: Session = Depends(get_db)) -> None:
    band = db.get(Band, band_id)
    if band is None:
        raise HTTPException(404, "band not found")
    if band.slug == "default":
        raise HTTPException(409, "the default band cannot be deleted")
    db.delete(band)
    db.commit()
