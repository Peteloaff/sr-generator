"""Band DNA - reference library, folder import, analysis, training manifest."""

from __future__ import annotations

import json
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from sr.common.storage import get_storage
from sr.db import get_db
from sr.models.band import Band
from sr.models.band_reference import BandReference
from sr.models.generation_job import GenerationJob
from sr.schemas.job import JobRead
from sr.schemas.reference import (
    FolderImportRequest,
    ManifestSnapshot,
    ReferenceDetail,
    ReferenceRead,
    ReferenceUpdate,
)
from sr.services.dna import band_dna
from sr.services.manifest import IncompleteManifest, build_manifest, completeness_report
from sr.services.references import analyze_reference, ingest_bytes
from sr.worker.queue import get_queue

router = APIRouter(tags=["band-dna"])


def _ref(db: Session, reference_id: str) -> BandReference:
    ref = db.get(BandReference, reference_id)
    if ref is None:
        raise HTTPException(404, "reference not found")
    return ref


@router.get("/bands/{band_id}/references", response_model=list[ReferenceRead])
def list_references(band_id: str, db: Session = Depends(get_db)) -> list[BandReference]:
    if db.get(Band, band_id) is None:
        raise HTTPException(404, "band not found")
    return list(
        db.scalars(
            select(BandReference)
            .where(BandReference.band_id == band_id)
            .order_by(BandReference.title)
        )
    )


@router.post("/bands/{band_id}/references", response_model=ReferenceRead, status_code=201)
async def upload_reference(
    band_id: str,
    analyze: bool = Query(default=True),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> BandReference:
    band = db.get(Band, band_id)
    if band is None:
        raise HTTPException(404, "band not found")
    data = await file.read()
    ref = ingest_bytes(
        db, band, title=(file.filename or "reference").rsplit(".", 1)[0],
        filename=file.filename or "reference.wav", data=data, source_kind="upload",
    )
    if ref is None:
        raise HTTPException(
            409, "this audio is already in the reference library (or is undecodable)"
        )
    if analyze:
        analyze_reference(db, ref)
    db.commit()
    db.refresh(ref)
    return ref


@router.post("/bands/{band_id}/references/import-folder", response_model=JobRead, status_code=201)
def import_folder_endpoint(
    band_id: str, body: FolderImportRequest, db: Session = Depends(get_db)
) -> GenerationJob:
    if db.get(Band, band_id) is None:
        raise HTTPException(404, "band not found")
    job = GenerationJob(
        job_type="import_folder", provider="catalogue-import", status="queued",
        parameters_json={"band_id": band_id, **body.model_dump()},
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    get_queue().enqueue(job.id)
    db.refresh(job)
    return job


@router.post("/bands/{band_id}/references/analyze", response_model=JobRead, status_code=201)
def analyze_band_endpoint(
    band_id: str, reanalyze: bool = Query(default=False), db: Session = Depends(get_db)
) -> GenerationJob:
    if db.get(Band, band_id) is None:
        raise HTTPException(404, "band not found")
    job = GenerationJob(
        job_type="analyze_reference", provider="analysis", status="queued",
        parameters_json={"band_id": band_id, "reanalyze": reanalyze},
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    get_queue().enqueue(job.id)
    db.refresh(job)
    return job


@router.get("/references/{reference_id}", response_model=ReferenceDetail)
def get_reference(reference_id: str, db: Session = Depends(get_db)) -> BandReference:
    return _ref(db, reference_id)


@router.patch("/references/{reference_id}", response_model=ReferenceDetail)
def update_reference(
    reference_id: str, payload: ReferenceUpdate, db: Session = Depends(get_db)
) -> BandReference:
    ref = _ref(db, reference_id)
    fields = payload.model_dump(exclude_unset=True)
    if fields.get("approved_for_training") and ref.analysis_status != "ready":
        raise HTTPException(422, "analyse the reference before approving it for training")
    for k, v in fields.items():
        setattr(ref, k, v)
    db.commit()
    db.refresh(ref)
    return ref


@router.post("/references/{reference_id}/analyze", response_model=ReferenceDetail)
def analyze_one(reference_id: str, db: Session = Depends(get_db)) -> BandReference:
    ref = analyze_reference(db, _ref(db, reference_id))
    db.commit()
    db.refresh(ref)
    return ref


@router.delete("/references/{reference_id}", status_code=204)
def delete_reference(reference_id: str, db: Session = Depends(get_db)) -> None:
    db.delete(_ref(db, reference_id))
    db.commit()


@router.get("/bands/{band_id}/dna")
def get_band_dna(band_id: str, db: Session = Depends(get_db)) -> dict:
    band = db.get(Band, band_id)
    if band is None:
        raise HTTPException(404, "band not found")
    return band_dna(db, band)


@router.get("/bands/{band_id}/training-manifest")
def get_training_manifest(
    band_id: str, strict: bool = Query(default=True), db: Session = Depends(get_db)
) -> dict:
    band = db.get(Band, band_id)
    if band is None:
        raise HTTPException(404, "band not found")
    try:
        return build_manifest(db, band, strict=strict)
    except IncompleteManifest as exc:
        raise HTTPException(
            409,
            detail={
                "error": "approved references are missing metadata",
                "incomplete": exc.incomplete,
            },
        ) from exc


@router.post("/bands/{band_id}/training-manifest", response_model=ManifestSnapshot, status_code=201)
def snapshot_training_manifest(band_id: str, db: Session = Depends(get_db)) -> ManifestSnapshot:
    band = db.get(Band, band_id)
    if band is None:
        raise HTTPException(404, "band not found")
    try:
        manifest = build_manifest(db, band, strict=True)
    except IncompleteManifest as exc:
        raise HTTPException(
            409, detail={"error": "incomplete", "incomplete": exc.incomplete}
        ) from exc

    storage = get_storage()
    existing = [
        k for k in storage.list(f"models/band/{band.id}/")
        if k.rsplit("/", 1)[-1].startswith("manifest_v") and k.endswith(".json")
    ]
    version = len(existing) + 1
    key = f"models/band/{band.id}/manifest_v{version}.json"
    manifest["snapshot_version"] = version
    manifest["snapshot_at"] = datetime.now(UTC).isoformat()
    storage.write_text(key, json.dumps(manifest, indent=2, sort_keys=True))
    return ManifestSnapshot(
        dataset_version=manifest["dataset_version"],
        snapshot_version=version,
        path=key,
        count=manifest["totals"]["count"],
    )


@router.get("/bands/{band_id}/training-manifest/completeness")
def manifest_completeness(band_id: str, db: Session = Depends(get_db)) -> list[dict]:
    band = db.get(Band, band_id)
    if band is None:
        raise HTTPException(404, "band not found")
    return completeness_report(db, band)
