"""Vocal presets - band-scoped, reusable vocal-stack recipes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from sr.api.deps import get_band
from sr.db import get_db
from sr.models.band import Band
from sr.models.song import SongSection
from sr.models.vocal import VocalRole
from sr.models.vocal_preset import VocalPreset
from sr.schemas.preset import ApplyRequest, ApplyResult, PresetCreate, PresetRead
from sr.services.presets import apply_to_section, capture_from_section

router = APIRouter(prefix="/vocal-presets", tags=["presets"])


@router.get("", response_model=list[PresetRead])
def list_presets(
    band: Band = Depends(get_band), db: Session = Depends(get_db)
) -> list[VocalPreset]:
    return list(
        db.scalars(
            select(VocalPreset).where(VocalPreset.band_id == band.id).order_by(VocalPreset.name)
        )
    )


@router.post("", response_model=PresetRead, status_code=201)
def create_preset(
    payload: PresetCreate, band: Band = Depends(get_band), db: Session = Depends(get_db)
) -> VocalPreset:
    if db.scalar(
        select(VocalPreset).where(
            VocalPreset.band_id == band.id, VocalPreset.name == payload.name
        )
    ):
        raise HTTPException(409, f"a preset named {payload.name!r} already exists")

    if payload.from_section_id:
        section = db.get(SongSection, payload.from_section_id)
        if section is None:
            raise HTTPException(404, "from_section_id not found")
        spec = capture_from_section(db, section)
    elif payload.spec is not None:
        spec = payload.spec
    else:
        raise HTTPException(422, "provide either from_section_id or spec")

    preset = VocalPreset(
        band_id=band.id, name=payload.name, description=payload.description, spec_json=spec
    )
    db.add(preset)
    db.commit()
    db.refresh(preset)
    return preset


@router.get("/{preset_id}", response_model=PresetRead)
def get_preset(preset_id: str, db: Session = Depends(get_db)) -> VocalPreset:
    preset = db.get(VocalPreset, preset_id)
    if preset is None:
        raise HTTPException(404, "preset not found")
    return preset


@router.delete("/{preset_id}", status_code=204)
def delete_preset(preset_id: str, db: Session = Depends(get_db)) -> None:
    preset = db.get(VocalPreset, preset_id)
    if preset is None:
        raise HTTPException(404, "preset not found")
    db.delete(preset)
    db.commit()


@router.post("/{preset_id}/apply", response_model=ApplyResult, status_code=201)
def apply_preset(
    preset_id: str, payload: ApplyRequest, db: Session = Depends(get_db)
) -> ApplyResult:
    preset = db.get(VocalPreset, preset_id)
    if preset is None:
        raise HTTPException(404, "preset not found")
    section = db.get(SongSection, payload.section_id)
    if section is None:
        raise HTTPException(404, "section not found")
    if section.song.band_id != preset.band_id:
        raise HTTPException(422, "preset and section belong to different bands")

    created, skipped = apply_to_section(db, section, preset.spec_json)
    roles = db.scalars(
        select(VocalRole)
        .options(selectinload(VocalRole.assignments))
        .where(VocalRole.id.in_([r.id for r in created] or [""]))
    )
    return ApplyResult(
        section_id=section.id, created_roles=list(roles), skipped_singers=skipped
    )
