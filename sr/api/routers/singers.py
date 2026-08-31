from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from sr.api.deps import get_band
from sr.db import get_db
from sr.models.band import Band
from sr.models.singer import Singer
from sr.schemas.singer import SingerCreate, SingerRead, SingerUpdate

router = APIRouter(prefix="/singers", tags=["singers"])


@router.get("", response_model=list[SingerRead])
def list_singers(band: Band = Depends(get_band), db: Session = Depends(get_db)) -> list[Singer]:
    return list(
        db.scalars(select(Singer).where(Singer.band_id == band.id).order_by(Singer.name))
    )


@router.post("", response_model=SingerRead, status_code=201)
def create_singer(
    payload: SingerCreate, band: Band = Depends(get_band), db: Session = Depends(get_db)
) -> Singer:
    band_id = payload.band_id or band.id
    if db.get(Band, band_id) is None:
        raise HTTPException(404, f"band {band_id!r} not found")
    if db.scalar(
        select(Singer).where(Singer.band_id == band_id, Singer.name == payload.name)
    ):
        raise HTTPException(409, f"singer named {payload.name!r} already exists in this band")
    data = payload.model_dump(exclude={"band_id"})
    singer = Singer(band_id=band_id, **data)
    db.add(singer)
    db.commit()
    db.refresh(singer)
    return singer


@router.get("/{singer_id}", response_model=SingerRead)
def get_singer(singer_id: str, db: Session = Depends(get_db)) -> Singer:
    singer = db.get(Singer, singer_id)
    if singer is None:
        raise HTTPException(404, "singer not found")
    return singer


@router.patch("/{singer_id}", response_model=SingerRead)
def update_singer(singer_id: str, payload: SingerUpdate, db: Session = Depends(get_db)) -> Singer:
    singer = db.get(Singer, singer_id)
    if singer is None:
        raise HTTPException(404, "singer not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(singer, field, value.value if hasattr(value, "value") else value)
    db.commit()
    db.refresh(singer)
    return singer


@router.delete("/{singer_id}", status_code=204)
def delete_singer(singer_id: str, db: Session = Depends(get_db)) -> None:
    singer = db.get(Singer, singer_id)
    if singer is None:
        raise HTTPException(404, "singer not found")
    db.delete(singer)
    db.commit()
