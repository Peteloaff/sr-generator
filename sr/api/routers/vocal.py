"""Vocal Director API: vocal roles and per-singer assignments.

Roles attach to a SongSection (default) or a single LyricLine (override).
Weights are stored raw; ``/normalized`` returns the 100%-scaled split and the
ensemble take allocation.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from sr.db import get_db
from sr.models.singer import Singer
from sr.models.song import LyricLine, SongSection
from sr.models.vocal import VocalAssignment, VocalRole
from sr.schemas.vocal import (
    NormalizedShare,
    VocalAssignmentCreate,
    VocalAssignmentRead,
    VocalAssignmentUpdate,
    VocalRoleCreate,
    VocalRoleRead,
    VocalRoleUpdate,
)
from sr.services.vocal import normalized_shares

router = APIRouter(tags=["vocal-director"])


def _role(db: Session, role_id: str) -> VocalRole:
    role = db.scalar(
        select(VocalRole)
        .options(selectinload(VocalRole.assignments))
        .where(VocalRole.id == role_id)
    )
    if role is None:
        raise HTTPException(404, "vocal role not found")
    return role


def _band_id_for_role(db: Session, role: VocalRole) -> str:
    if role.section_id:
        section = db.get(SongSection, role.section_id)
        return section.song.band_id
    line = db.get(LyricLine, role.lyric_line_id)
    return line.song.band_id


def _check_singer(db: Session, singer_id: str, band_id: str) -> None:
    singer = db.get(Singer, singer_id)
    if singer is None:
        raise HTTPException(404, f"singer {singer_id!r} not found")
    if singer.band_id != band_id:
        raise HTTPException(422, "singer belongs to a different band")


def _create_role(
    db: Session, payload: VocalRoleCreate, band_id: str, **parent: str
) -> VocalRole:
    role = VocalRole(
        role_type=payload.role_type.value,
        ensemble_size=payload.ensemble_size,
        width=payload.width,
        humanize_timing_ms=payload.humanize_timing_ms,
        humanize_pitch_cents=payload.humanize_pitch_cents,
        humanize_formant=payload.humanize_formant,
        notes=payload.notes,
        processing_json=payload.processing,
        **parent,
    )
    for a in payload.assignments:
        _check_singer(db, a.singer_id, band_id)
        role.assignments.append(VocalAssignment(**a.model_dump()))
    db.add(role)
    db.commit()
    db.refresh(role)
    return role


@router.post("/sections/{section_id}/roles", response_model=VocalRoleRead, status_code=201)
def create_section_role(
    section_id: str, payload: VocalRoleCreate, db: Session = Depends(get_db)
) -> VocalRole:
    section = db.get(SongSection, section_id)
    if section is None:
        raise HTTPException(404, "section not found")
    return _create_role(db, payload, section.song.band_id, section_id=section_id)


@router.get("/sections/{section_id}/roles", response_model=list[VocalRoleRead])
def list_section_roles(section_id: str, db: Session = Depends(get_db)) -> list[VocalRole]:
    if db.get(SongSection, section_id) is None:
        raise HTTPException(404, "section not found")
    return list(
        db.scalars(
            select(VocalRole)
            .options(selectinload(VocalRole.assignments))
            .where(VocalRole.section_id == section_id)
        )
    )


@router.post("/lines/{line_id}/roles", response_model=VocalRoleRead, status_code=201)
def create_line_role(
    line_id: str, payload: VocalRoleCreate, db: Session = Depends(get_db)
) -> VocalRole:
    line = db.get(LyricLine, line_id)
    if line is None:
        raise HTTPException(404, "line not found")
    return _create_role(db, payload, line.song.band_id, lyric_line_id=line_id)


@router.get("/lines/{line_id}/roles", response_model=list[VocalRoleRead])
def list_line_roles(line_id: str, db: Session = Depends(get_db)) -> list[VocalRole]:
    if db.get(LyricLine, line_id) is None:
        raise HTTPException(404, "line not found")
    return list(
        db.scalars(
            select(VocalRole)
            .options(selectinload(VocalRole.assignments))
            .where(VocalRole.lyric_line_id == line_id)
        )
    )


@router.get("/roles/{role_id}", response_model=VocalRoleRead)
def get_role(role_id: str, db: Session = Depends(get_db)) -> VocalRole:
    return _role(db, role_id)


@router.patch("/roles/{role_id}", response_model=VocalRoleRead)
def update_role(
    role_id: str, payload: VocalRoleUpdate, db: Session = Depends(get_db)
) -> VocalRole:
    role = _role(db, role_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        col = "processing_json" if field == "processing" else field
        setattr(role, col, value.value if hasattr(value, "value") else value)
    db.commit()
    db.refresh(role)
    return role


@router.delete("/roles/{role_id}", status_code=204)
def delete_role(role_id: str, db: Session = Depends(get_db)) -> None:
    db.delete(_role(db, role_id))
    db.commit()


@router.get("/roles/{role_id}/normalized", response_model=list[NormalizedShare])
def get_normalized(role_id: str, db: Session = Depends(get_db)) -> list[NormalizedShare]:
    return normalized_shares(_role(db, role_id))


@router.post("/roles/{role_id}/assignments", response_model=VocalAssignmentRead, status_code=201)
def add_assignment(
    role_id: str, payload: VocalAssignmentCreate, db: Session = Depends(get_db)
) -> VocalAssignment:
    role = _role(db, role_id)
    _check_singer(db, payload.singer_id, _band_id_for_role(db, role))
    if any(a.singer_id == payload.singer_id for a in role.assignments):
        raise HTTPException(409, "singer already assigned to this role")
    assignment = VocalAssignment(vocal_role_id=role_id, **payload.model_dump())
    db.add(assignment)
    db.commit()
    db.refresh(assignment)
    return assignment


@router.patch("/assignments/{assignment_id}", response_model=VocalAssignmentRead)
def update_assignment(
    assignment_id: str, payload: VocalAssignmentUpdate, db: Session = Depends(get_db)
) -> VocalAssignment:
    assignment = db.get(VocalAssignment, assignment_id)
    if assignment is None:
        raise HTTPException(404, "assignment not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(assignment, field, value)
    db.commit()
    db.refresh(assignment)
    return assignment


@router.delete("/assignments/{assignment_id}", status_code=204)
def delete_assignment(assignment_id: str, db: Session = Depends(get_db)) -> None:
    assignment = db.get(VocalAssignment, assignment_id)
    if assignment is None:
        raise HTTPException(404, "assignment not found")
    db.delete(assignment)
    db.commit()
