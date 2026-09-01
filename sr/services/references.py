"""Reference-song ingest: single upload and folder import + analysis."""

from __future__ import annotations

import hashlib
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from sr.common import audio
from sr.common.storage import get_storage
from sr.models.band import Band
from sr.models.band_reference import BandReference
from sr.models.generation_job import GenerationJob
from sr.providers.registry import get_provider
from sr.services.quality import check_file
from sr.worker.progress import report as report_progress

AUDIO_SUFFIXES = audio.SUPPORTED_SUFFIXES


def _hash_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()[:32]


def ingest_bytes(
    db: Session, band: Band, *, title: str, filename: str, data: bytes, source_kind: str,
    source_file: str | None = None,
) -> BandReference | None:
    """Create a BandReference from raw audio bytes. Returns None if it is a
    content-hash duplicate already in the band."""
    content_hash = _hash_bytes(data)
    if db.scalar(
        select(BandReference).where(
            BandReference.band_id == band.id, BandReference.content_hash == content_hash
        )
    ):
        return None
    base = f"references/{band.id}/catalogue/{content_hash}"
    try:
        ing = audio.ingest_upload(get_storage(), base, filename, data)
    except ValueError:
        return None
    ref = BandReference(
        band_id=band.id, title=title, source_file=source_file, source_kind=source_kind,
        content_hash=content_hash, duration=ing.info.duration,
        sample_rate=ing.info.sample_rate, channels=ing.info.channels,
        analysis_status="none",
    )
    db.add(ref)
    db.flush()
    return ref


def import_folder(
    db: Session, job: GenerationJob, *, band_id: str, params: dict
) -> dict:
    band = db.get(Band, band_id)
    if band is None:
        raise LookupError(f"band {band_id} not found")
    root = Path(params["path"]).expanduser()
    if not root.is_dir():
        raise ValueError(f"not a directory: {root}")
    recursive = bool(params.get("recursive", True))
    auto_approve = bool(params.get("auto_approve", False))

    files = sorted(
        p for p in (root.rglob("*") if recursive else root.iterdir())
        if p.is_file() and p.suffix.lower() in AUDIO_SUFFIXES
    )
    if not files:
        raise ValueError(f"no audio files under {root}")

    created, skipped, failed = [], 0, 0
    for i, path in enumerate(files):
        report_progress(db, job, 0.05 + 0.9 * i / len(files), f"{path.name}")
        try:
            ref = ingest_bytes(
                db, band, title=path.stem, filename=path.name, data=path.read_bytes(),
                source_kind="folder", source_file=str(path),
            )
        except Exception:  # noqa: BLE001 - one bad file shouldn't abort the import
            failed += 1
            continue
        if ref is None:
            skipped += 1
            continue
        analyze_reference(db, ref)
        clean = ref.analysis_status == "ready" and (ref.quality_json or {}).get("passed")
        if auto_approve and clean:
            ref.approved_for_training = True
        created.append(ref.id)

    db.flush()
    return {
        "band_id": band_id, "root": str(root), "scanned": len(files),
        "created": len(created), "skipped_duplicates": skipped, "failed": failed,
        "reference_ids": created,
    }


def analyze_reference(db: Session, ref: BandReference) -> BandReference:
    """Run analysis + quality on one reference (in-process, on the given session)."""
    storage = get_storage()
    canonical_key = f"references/{ref.band_id}/catalogue/{ref.content_hash}/canonical.wav"
    if not storage.exists(canonical_key):
        ref.analysis_status = "failed"
        ref.notes = (ref.notes or "") + " [canonical audio missing]"
        return ref
    try:
        canonical = storage.ensure_local(canonical_key)
        provider = get_provider("analysis")
        result = provider.analyze(source_path=canonical)
        a = result.analysis
        ref.analysis_json = a
        ref.analysis_provider = result.provider
        ref.analysis_version = result.provider_version
        ref.bpm = a.get("bpm") or ref.bpm
        ref.key = (a.get("key") or {}).get("key") or ref.key
        ref.tuning = (a.get("tuning") or {}).get("label") or ref.tuning
        ref.structure_json = a.get("structure")
        ref.duration = a.get("duration") or ref.duration
        ref.quality_json = check_file(canonical)
        ref.analysis_status = "ready"
    except Exception as exc:  # noqa: BLE001
        ref.analysis_status = "failed"
        ref.notes = (ref.notes or "") + f" [analysis failed: {exc}]"
    return ref


def analyze_band_job(
    db: Session, job: GenerationJob, *, band_id: str, params: dict
) -> dict:
    """Analyze one reference (params['reference_id']) or every un-analysed one."""
    ref_id = params.get("reference_id")
    if ref_id:
        refs = [r for r in [db.get(BandReference, ref_id)] if r is not None]
    else:
        stmt = select(BandReference).where(BandReference.band_id == band_id)
        if not params.get("reanalyze"):
            stmt = stmt.where(BandReference.analysis_status != "ready")
        refs = list(db.scalars(stmt))
    for i, ref in enumerate(refs):
        report_progress(db, job, 0.05 + 0.9 * i / max(1, len(refs)), ref.title)
        analyze_reference(db, ref)
    db.flush()
    return {
        "band_id": band_id,
        "analyzed": [r.id for r in refs],
        "ready": sum(1 for r in refs if r.analysis_status == "ready"),
        "failed": sum(1 for r in refs if r.analysis_status == "failed"),
    }
