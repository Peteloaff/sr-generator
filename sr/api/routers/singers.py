from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from sr.db import get_db
from sr.models.singer import Singer
from sr.schemas.singer import SingerCreate, SingerRead, SingerUpdate

router = APIRouter(prefix="/singers", tags=["singers"])


@router.get("", response_model=list[SingerRead])
def list_singers(db: Session = Depends(get_db)) -> list[Singer]:
    return list(db.scalars(select(Singer).order_by(Singer.name)))


@router.post("", response_model=SingerRead, status_code=201)
def create_singer(payload: SingerCreate, db: Session = Depends(get_db)) -> Singer:
    if db.scalar(select(Singer).where(Singer.name == payload.name)):
        raise HTTPException(409, f"singer named {payload.name!r} already exists")
    singer = Singer(**payload.model_dump())
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
