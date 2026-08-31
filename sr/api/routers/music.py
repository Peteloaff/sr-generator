"""Stage 7 - band adapter training + band-specific instrumental generation."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from sr.db import get_db
from sr.models.band import Band
from sr.models.band_adapter import BandAdapter
from sr.models.generation_job import GenerationJob
from sr.models.song import Song, SongSection
from sr.schemas.adapter import AdapterRead, AdapterTrainRequest, GenerateInstrumentalRequest
from sr.schemas.job import JobRead
from sr.worker.queue import get_queue

router = APIRouter(tags=["music"])


@router.post("/bands/{band_id}/adapters/train", response_model=JobRead, status_code=201)
def train_adapter(
    band_id: str, body: AdapterTrainRequest, db: Session = Depends(get_db)
) -> GenerationJob:
    if db.get(Band, band_id) is None:
        raise HTTPException(404, "band not found")
    job = GenerationJob(
        job_type="train_band_adapter", provider="music", status="queued",
        parameters_json={"band_id": band_id, **body.model_dump(exclude_none=True)},
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    get_queue().enqueue(job.id)
    db.refresh(job)
    return job


@router.get("/bands/{band_id}/adapters", response_model=list[AdapterRead])
def list_adapters(band_id: str, db: Session = Depends(get_db)) -> list[BandAdapter]:
    if db.get(Band, band_id) is None:
        raise HTTPException(404, "band not found")
    return list(
        db.scalars(
            select(BandAdapter)
            .where(BandAdapter.band_id == band_id)
            .order_by(BandAdapter.created_at.desc())
        )
    )


@router.get("/adapters/{adapter_id}", response_model=AdapterRead)
def get_adapter(adapter_id: str, db: Session = Depends(get_db)) -> BandAdapter:
    adapter = db.get(BandAdapter, adapter_id)
    if adapter is None:
        raise HTTPException(404, "adapter not found")
    return adapter


@router.delete("/adapters/{adapter_id}", status_code=204)
def delete_adapter(adapter_id: str, db: Session = Depends(get_db)) -> None:
    adapter = db.get(BandAdapter, adapter_id)
    if adapter is None:
        raise HTTPException(404, "adapter not found")
    db.delete(adapter)
    db.commit()


@router.post(
    "/songs/{song_id}/sections/{section_id}/generate-instrumental",
    response_model=JobRead,
    status_code=201,
)
def generate_instrumental(
    song_id: str,
    section_id: str,
    body: GenerateInstrumentalRequest,
    db: Session = Depends(get_db),
) -> GenerationJob:
    section = db.get(SongSection, section_id)
    if section is None or section.song_id != song_id:
        raise HTTPException(404, "section not found")
    seed = body.seed if body.seed is not None else (section.generation_seed or section.song.seed)
    job = GenerationJob(
        job_type="generate_music", song_id=song_id, section_id=section_id,
        seed=seed, provider="music", status="queued",
        parameters_json=body.model_dump(exclude={"seed"}, exclude_none=True),
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    get_queue().enqueue(job.id)
    db.refresh(job)
    return job


@router.get(
    "/songs/{song_id}/sections/{section_id}/generations", response_model=list[JobRead]
)
def list_generations(
    song_id: str, section_id: str, db: Session = Depends(get_db)
) -> list[GenerationJob]:
    if db.get(Song, song_id) is None:
        raise HTTPException(404, "song not found")
    return list(
        db.scalars(
            select(GenerationJob)
            .options(selectinload(GenerationJob.outputs))
            .where(
                GenerationJob.section_id == section_id,
                GenerationJob.job_type == "generate_music",
            )
            .order_by(GenerationJob.created_at.desc())
        )
    )
