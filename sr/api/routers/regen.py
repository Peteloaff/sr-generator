"""Stage 9 - surgical regeneration: section / role regen, lock, revisions, rollback."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from sr.db import get_db
from sr.models.generation_job import GenerationJob
from sr.models.section_revision import SectionRevision
from sr.models.song import SongSection
from sr.models.vocal import VocalRole
from sr.schemas.compose import (
    RegenerateRoleRequest,
    RegenerateSectionRequest,
    RollbackRequest,
)
from sr.schemas.job import JobRead
from sr.schemas.vocal import VocalRoleRead
from sr.services import regen as regen_svc
from sr.worker.queue import get_queue

router = APIRouter(tags=["surgical-regen"])


def _section(db: Session, section_id: str) -> SongSection:
    section = db.get(SongSection, section_id)
    if section is None:
        raise HTTPException(404, "section not found")
    return section


@router.post("/sections/{section_id}/lock", response_model=dict)
def set_lock(
    section_id: str, locked: bool = Query(default=True), db: Session = Depends(get_db)
) -> dict:
    section = _section(db, section_id)
    section.locked = locked
    db.commit()
    return {"section_id": section_id, "locked": section.locked}


@router.post("/sections/{section_id}/regenerate", response_model=JobRead, status_code=201)
def regenerate_section(
    section_id: str, body: RegenerateSectionRequest, db: Session = Depends(get_db)
) -> GenerationJob:
    section = _section(db, section_id)
    if section.locked:
        raise HTTPException(423, "section is locked; unlock it first")
    if not any(r.assignments for r in section.vocal_roles):
        raise HTTPException(422, "section has no vocal roles with assignments")
    seed = (
        body.seed if body.seed is not None
        else (section.generation_seed or section.song.seed or 0)
    )
    job = GenerationJob(
        job_type="regenerate_section", song_id=section.song_id, section_id=section_id,
        seed=seed, provider="regen-engine", status="queued",
        parameters_json=body.model_dump(exclude_none=True),
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    get_queue().enqueue(job.id)
    db.refresh(job)
    return job


@router.post("/roles/{role_id}/regenerate", response_model=JobRead, status_code=201)
def regenerate_role(
    role_id: str, body: RegenerateRoleRequest, db: Session = Depends(get_db)
) -> GenerationJob:
    role = db.get(VocalRole, role_id)
    if role is None:
        raise HTTPException(404, "role not found")
    if role.section_id is None:
        raise HTTPException(422, "only section-scoped roles support isolated regeneration")
    section = db.get(SongSection, role.section_id)
    if section.locked:
        raise HTTPException(423, "section is locked; unlock it first")
    seed = (
        body.seed if body.seed is not None
        else (section.generation_seed or section.song.seed or 0)
    )
    params = body.model_dump(exclude_none=True)
    params["role_id"] = role_id
    job = GenerationJob(
        job_type="regenerate_role", song_id=section.song_id, section_id=section.id,
        seed=seed, provider="regen-engine", status="queued", parameters_json=params,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    get_queue().enqueue(job.id)
    db.refresh(job)
    return job


@router.get("/sections/{section_id}/revisions")
def list_revisions(section_id: str, db: Session = Depends(get_db)) -> list[dict]:
    _section(db, section_id)
    revs = db.scalars(
        select(SectionRevision)
        .where(SectionRevision.section_id == section_id)
        .order_by(SectionRevision.revision.desc())
    )
    return [
        {
            "id": r.id, "revision": r.revision, "kind": r.kind,
            "render_job_id": r.render_job_id, "changed_role_id": r.changed_role_id,
            "note": r.note, "is_current": r.is_current,
            "roles": len(r.roles_snapshot_json or []),
            "created_at": r.created_at.isoformat(),
        }
        for r in revs
    ]


@router.post("/sections/{section_id}/rollback", response_model=list[VocalRoleRead])
def rollback(
    section_id: str, body: RollbackRequest, db: Session = Depends(get_db)
) -> list[VocalRole]:
    section = _section(db, section_id)
    try:
        regen_svc.rollback_section(db, section, body.revision)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(423, str(exc)) from exc
    return list(
        db.scalars(
            select(VocalRole)
            .options(selectinload(VocalRole.assignments))
            .where(VocalRole.section_id == section_id)
        )
    )
