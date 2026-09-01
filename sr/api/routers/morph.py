"""Stage 11 - experimental vocal morph. Every route is gated by SR_EXPERIMENTAL_MORPH."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from sr.config import get_settings
from sr.db import get_db
from sr.models.generation_job import GenerationJob
from sr.models.singer import Singer
from sr.models.song import SongSection
from sr.models.vocal_morph import VocalMorph
from sr.schemas.compose import MorphCreate
from sr.schemas.job import JobRead
from sr.worker.queue import get_queue

router = APIRouter(tags=["experimental-morph"])


def _require_flag() -> None:
    if not get_settings().experimental_morph:
        raise HTTPException(
            403,
            "vocal morph is an experimental feature and is disabled "
            "(set SR_EXPERIMENTAL_MORPH=true to enable)",
        )


def _morph(db: Session, morph_id: str) -> VocalMorph:
    m = db.get(VocalMorph, morph_id)
    if m is None:
        raise HTTPException(404, "morph not found")
    return m


@router.get("/experimental")
def experimental_status() -> dict:
    """Unauthenticated feature probe so the UI can hide the lane."""
    return {"morph_enabled": get_settings().experimental_morph}


@router.post("/sections/{section_id}/morphs", status_code=201)
def create_morph(
    section_id: str, body: MorphCreate, db: Session = Depends(get_db)
) -> dict:
    _require_flag()
    section = db.get(SongSection, section_id)
    if section is None or section_id != body.section_id:
        raise HTTPException(404, "section not found")
    for sid in (body.from_singer_id, body.to_singer_id):
        s = db.get(Singer, sid)
        if s is None or s.band_id != section.song.band_id:
            raise HTTPException(422, f"singer {sid!r} not in this band")
    if body.from_singer_id == body.to_singer_id:
        raise HTTPException(422, "from and to singers must differ")
    if body.end_frac <= body.start_frac:
        raise HTTPException(422, "end_frac must be greater than start_frac")
    morph = VocalMorph(
        section_id=section_id, from_singer_id=body.from_singer_id,
        to_singer_id=body.to_singer_id, curve=body.curve,
        start_frac=body.start_frac, end_frac=body.end_frac,
    )
    db.add(morph)
    db.commit()
    db.refresh(morph)
    return _view(morph)


@router.get("/sections/{section_id}/morphs")
def list_morphs(section_id: str, db: Session = Depends(get_db)) -> list[dict]:
    _require_flag()
    if db.get(SongSection, section_id) is None:
        raise HTTPException(404, "section not found")
    return [
        _view(m)
        for m in db.scalars(
            select(VocalMorph).where(VocalMorph.section_id == section_id)
        )
    ]


@router.post("/morphs/{morph_id}/preview", response_model=JobRead, status_code=201)
def preview_morph(morph_id: str, db: Session = Depends(get_db)) -> GenerationJob:
    _require_flag()
    morph = _morph(db, morph_id)
    section = db.get(SongSection, morph.section_id)
    job = GenerationJob(
        job_type="morph_preview", song_id=section.song_id, section_id=section.id,
        provider="morph-rnd", status="queued", parameters_json={"morph_id": morph_id},
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    get_queue().enqueue(job.id)
    db.refresh(job)
    return job


@router.post("/morphs/{morph_id}/commit")
def commit_morph(morph_id: str, db: Session = Depends(get_db)) -> dict:
    _require_flag()
    morph = _morph(db, morph_id)
    q = morph.quality_json or {}
    if not q:
        raise HTTPException(409, "preview the morph before committing")
    if not q.get("usable"):
        raise HTTPException(
            409,
            f"morph quality is not reliable (score {q.get('score')}, "
            f"flags {q.get('flags')}); it cannot be committed",
        )
    morph.committed = True
    db.commit()
    return _view(morph)


@router.delete("/morphs/{morph_id}", status_code=204)
def delete_morph(morph_id: str, db: Session = Depends(get_db)) -> None:
    _require_flag()
    db.delete(_morph(db, morph_id))
    db.commit()


def _view(m: VocalMorph) -> dict:
    return {
        "id": m.id, "section_id": m.section_id,
        "from_singer_id": m.from_singer_id, "to_singer_id": m.to_singer_id,
        "curve": m.curve, "start_frac": m.start_frac, "end_frac": m.end_frac,
        "quality": m.quality_json, "preview_asset_id": m.preview_asset_id,
        "committed": m.committed,
    }
