from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from sr.db import get_db
from sr.models.generation_job import GenerationJob
from sr.schemas.job import JobCreate, JobRead
from sr.worker.queue import get_queue

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("", response_model=list[JobRead])
def list_jobs(
    status: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[GenerationJob]:
    stmt = select(GenerationJob).options(selectinload(GenerationJob.outputs))
    if status:
        stmt = stmt.where(GenerationJob.status == status)
    return list(db.scalars(stmt.order_by(GenerationJob.created_at.desc())))


@router.post("", response_model=JobRead, status_code=201)
def create_job(payload: JobCreate, db: Session = Depends(get_db)) -> GenerationJob:
    job = GenerationJob(
        job_type=payload.job_type.value,
        song_id=payload.song_id,
        section_id=payload.section_id,
        seed=payload.seed,
        parameters_json=payload.parameters,
        input_asset_ids=payload.input_asset_ids,
        status="queued",
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    get_queue().enqueue(job.id)

    db.refresh(job)
    return job


@router.get("/{job_id}", response_model=JobRead)
def get_job(job_id: str, db: Session = Depends(get_db)) -> GenerationJob:
    job = db.scalar(
        select(GenerationJob)
        .options(selectinload(GenerationJob.outputs))
        .where(GenerationJob.id == job_id)
    )
    if job is None:
        raise HTTPException(404, "job not found")
    return job


@router.post("/{job_id}/wait", response_model=JobRead)
def wait_for_job(
    job_id: str, timeout: float = Query(default=30.0, le=120.0), db: Session = Depends(get_db)
) -> GenerationJob:
    if db.get(GenerationJob, job_id) is None:
        raise HTTPException(404, "job not found")
    try:
        get_queue().wait(job_id, timeout=timeout)
    except TimeoutError as exc:
        raise HTTPException(504, str(exc)) from exc
    return get_job(job_id, db)


@router.post("/{job_id}/retry", response_model=JobRead)
def retry_job(job_id: str, db: Session = Depends(get_db)) -> GenerationJob:
    job = db.get(GenerationJob, job_id)
    if job is None:
        raise HTTPException(404, "job not found")
    if job.status not in ("failed", "cancelled"):
        raise HTTPException(409, f"job is {job.status}; only failed/cancelled can retry")
    job.status = "queued"
    job.error = None
    db.commit()
    get_queue().enqueue(job_id)
    db.refresh(job)
    return job
