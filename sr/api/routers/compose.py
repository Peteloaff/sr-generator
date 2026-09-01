"""Stage 8 - full song generator: prompt -> structured, editable project."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from sr.db import get_db
from sr.models.band import Band
from sr.models.generation_job import GenerationJob
from sr.models.song import Song
from sr.schemas.compose import FullSongRequest
from sr.schemas.job import JobRead
from sr.services import songplan
from sr.services.dna import band_dna
from sr.worker.queue import get_queue

router = APIRouter(prefix="/songs", tags=["compose"])


def _song(db: Session, song_id: str) -> Song:
    song = db.get(Song, song_id)
    if song is None:
        raise HTTPException(404, "song not found")
    return song


@router.get("/{song_id}/plan")
def preview_plan(
    song_id: str,
    prompt: str | None = Query(default=None),
    seed: int = Query(default=0),
    db: Session = Depends(get_db),
) -> dict:
    """Dry-run the planner: returns the structure it *would* build. Mutates nothing."""
    song = _song(db, song_id)
    return songplan.plan_song(
        prompt=prompt or song.prompt or song.title,
        lyrics=song.lyrics,
        bpm=song.bpm,
        seed=seed or song.seed or 0,
        dna=band_dna(db, db.get(Band, song.band_id)),
    )


@router.post("/{song_id}/generate", response_model=JobRead, status_code=201)
def generate_full_song(
    song_id: str, body: FullSongRequest, db: Session = Depends(get_db)
) -> GenerationJob:
    song = _song(db, song_id)
    seed = body.seed if body.seed is not None else (song.seed or 0)
    job = GenerationJob(
        job_type="generate_song", song_id=song_id, seed=seed,
        provider="song-planner", status="queued",
        parameters_json=body.model_dump(exclude_none=True),
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    get_queue().enqueue(job.id)
    db.refresh(job)
    return job


@router.get("/{song_id}/generations", response_model=list[JobRead])
def list_song_generations(song_id: str, db: Session = Depends(get_db)) -> list[GenerationJob]:
    _song(db, song_id)
    return list(
        db.scalars(
            select(GenerationJob)
            .options(selectinload(GenerationJob.outputs))
            .where(
                GenerationJob.song_id == song_id,
                GenerationJob.job_type == "generate_song",
            )
            .order_by(GenerationJob.created_at.desc())
        )
    )
