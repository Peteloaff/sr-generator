from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from sr.api.deps import get_band
from sr.db import get_db
from sr.models.band import Band
from sr.models.project import Project
from sr.schemas.project import ProjectCreate, ProjectRead, ProjectUpdate
from sr.services.project_io import export_project, import_project

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("", response_model=list[ProjectRead])
def list_projects(band: Band = Depends(get_band), db: Session = Depends(get_db)) -> list[Project]:
    return list(
        db.scalars(
            select(Project).where(Project.band_id == band.id).order_by(Project.created_at)
        )
    )


@router.post("", response_model=ProjectRead, status_code=201)
def create_project(
    payload: ProjectCreate, band: Band = Depends(get_band), db: Session = Depends(get_db)
) -> Project:
    project = Project(band_id=band.id, **payload.model_dump())
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


@router.get("/{project_id}", response_model=ProjectRead)
def get_project(project_id: str, db: Session = Depends(get_db)) -> Project:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(404, "project not found")
    return project


@router.patch("/{project_id}", response_model=ProjectRead)
def update_project(
    project_id: str, payload: ProjectUpdate, db: Session = Depends(get_db)
) -> Project:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(404, "project not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(project, field, value)
    db.commit()
    db.refresh(project)
    return project


@router.delete("/{project_id}", status_code=204)
def delete_project(project_id: str, db: Session = Depends(get_db)) -> None:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(404, "project not found")
    db.delete(project)
    db.commit()


@router.get("/{project_id}/export")
def export_project_state(project_id: str, db: Session = Depends(get_db)) -> dict:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(404, "project not found")
    return export_project(db, project)


@router.post("/import", response_model=ProjectRead, status_code=201)
def import_project_state(
    payload: dict, band: Band = Depends(get_band), db: Session = Depends(get_db)
) -> Project:
    try:
        return import_project(db, band, payload)
    except (KeyError, ValueError) as exc:
        raise HTTPException(422, f"invalid project export: {exc}") from exc
