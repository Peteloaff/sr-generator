"""Stage 2 - source takes, section render, stem download."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from sr.common import audio
from sr.common.storage import get_storage
from sr.db import get_db
from sr.models.audio_asset import AudioAsset
from sr.models.generation_job import GenerationJob
from sr.models.render_take import RenderTake
from sr.models.singer import Singer
from sr.models.song import Song, SongSection
from sr.schemas.audio import AudioAssetRead
from sr.schemas.job import JobRead
from sr.schemas.render import ABResult, RenderRequest, RenderTakeRead
from sr.services.consent import blocked_for_generation
from sr.worker.queue import get_queue

router = APIRouter(prefix="/songs", tags=["render"])


def _section(db: Session, song_id: str, section_id: str) -> SongSection:
    section = db.get(SongSection, section_id)
    if section is None or section.song_id != song_id:
        raise HTTPException(404, "section not found")
    return section


def _song(db: Session, song_id: str) -> Song:
    song = db.get(Song, song_id)
    if song is None:
        raise HTTPException(404, "song not found")
    return song


@router.post(
    "/{song_id}/sections/{section_id}/takes", response_model=AudioAssetRead, status_code=201
)
async def upload_source_take(
    song_id: str,
    section_id: str,
    singer_id: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> AudioAsset:
    section = _section(db, song_id, section_id)
    singer = db.get(Singer, singer_id)
    if singer is None or singer.band_id != section.song.band_id:
        raise HTTPException(422, "singer not found in this band")

    existing = db.scalar(
        select(AudioAsset).where(
            AudioAsset.section_id == section_id,
            AudioAsset.singer_id == singer_id,
            AudioAsset.asset_type == "source_take",
        )
    )
    data = await file.read()
    base = f"references/{section.song.band_id}/{song_id}/{section_id}/takes/{singer_id}"
    try:
        ing = audio.ingest_upload(get_storage(), base, file.filename or "take", data)
    except ValueError as exc:
        raise HTTPException(415 if "unsupported" in str(exc) else 422, str(exc)) from exc

    if existing is not None:
        db.delete(existing)
        db.flush()
    asset = AudioAsset(
        song_id=song_id, section_id=section_id, singer_id=singer_id,
        asset_type="source_take", file_path=ing.original_key,
        label=f"{singer.name} — source take",
        sample_rate=ing.info.sample_rate, channels=ing.info.channels, duration=ing.info.duration,
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)
    return asset


@router.get("/{song_id}/sections/{section_id}/takes", response_model=list[AudioAssetRead])
def list_source_takes(
    song_id: str, section_id: str, db: Session = Depends(get_db)
) -> list[AudioAsset]:
    _section(db, song_id, section_id)
    return list(
        db.scalars(
            select(AudioAsset).where(
                AudioAsset.section_id == section_id, AudioAsset.asset_type == "source_take"
            )
        )
    )


@router.post(
    "/{song_id}/sections/{section_id}/instrumental", response_model=AudioAssetRead, status_code=201
)
async def upload_instrumental(
    song_id: str, section_id: str, file: UploadFile = File(...), db: Session = Depends(get_db)
) -> AudioAsset:
    section = _section(db, song_id, section_id)
    for old in db.scalars(
        select(AudioAsset).where(
            AudioAsset.section_id == section_id, AudioAsset.asset_type == "instrumental_bed"
        )
    ):
        db.delete(old)
    db.flush()
    data = await file.read()
    base = f"references/{section.song.band_id}/{song_id}/{section_id}/instrumental"
    try:
        ing = audio.ingest_upload(get_storage(), base, file.filename or "instr", data)
    except ValueError as exc:
        raise HTTPException(415 if "unsupported" in str(exc) else 422, str(exc)) from exc
    asset = AudioAsset(
        song_id=song_id, section_id=section_id, asset_type="instrumental_bed",
        file_path=ing.original_key, label="instrumental bed",
        sample_rate=ing.info.sample_rate, channels=ing.info.channels, duration=ing.info.duration,
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)
    return asset


@router.post(
    "/{song_id}/sections/{section_id}/guide", response_model=AudioAssetRead, status_code=201
)
async def upload_guide_vocal(
    song_id: str, section_id: str, file: UploadFile = File(...), db: Session = Depends(get_db)
) -> AudioAsset:
    section = _section(db, song_id, section_id)
    for old in db.scalars(
        select(AudioAsset).where(
            AudioAsset.section_id == section_id, AudioAsset.asset_type == "guide_vocal"
        )
    ):
        db.delete(old)
    db.flush()
    data = await file.read()
    base = f"references/{section.song.band_id}/{song_id}/{section_id}/guide"
    try:
        ing = audio.ingest_upload(get_storage(), base, file.filename or "guide", data)
    except ValueError as exc:
        raise HTTPException(415 if "unsupported" in str(exc) else 422, str(exc)) from exc
    asset = AudioAsset(
        song_id=song_id, section_id=section_id, asset_type="guide_vocal",
        file_path=ing.original_key, label="guide vocal",
        sample_rate=ing.info.sample_rate, channels=ing.info.channels, duration=ing.info.duration,
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)
    return asset


@router.post("/{song_id}/sections/{section_id}/render", response_model=JobRead, status_code=201)
def render_section_endpoint(
    song_id: str, section_id: str, body: RenderRequest, db: Session = Depends(get_db)
) -> GenerationJob:
    return _queue_render(db, *_check_renderable(db, song_id, section_id), body)


def _check_renderable(db: Session, song_id: str, section_id: str):
    section = _section(db, song_id, section_id)
    if not any(r.assignments for r in section.vocal_roles):
        raise HTTPException(422, "section has no vocal roles with singer assignments")
    assigned = {a.singer_id for r in section.vocal_roles for a in r.assignments}
    singers = list(db.scalars(select(Singer).where(Singer.id.in_(assigned))))
    blocked = blocked_for_generation(singers)
    if blocked:
        raise HTTPException(
            403,
            f"consent_generation is not authorized for: {', '.join(blocked)}. "
            "Grant it on the singer before rendering.",
        )
    return song_id, section_id, section


def _queue_render(db, song_id, section_id, section, body: RenderRequest) -> GenerationJob:
    seed = body.seed if body.seed is not None else (section.generation_seed or section.song.seed)
    params = {"mode": body.mode}
    if body.duration is not None:
        params["duration"] = body.duration
    job = GenerationJob(
        job_type="render_section", song_id=song_id, section_id=section_id,
        seed=seed, provider="layering-engine", status="queued", parameters_json=params,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    get_queue().enqueue(job.id)
    db.refresh(job)
    return job


@router.post("/{song_id}/sections/{section_id}/ab", response_model=ABResult)
def render_ab(
    song_id: str, section_id: str, body: RenderRequest, db: Session = Depends(get_db)
) -> ABResult:
    """Render the section twice - naive 'flat' stack vs full 'ensemble' - and
    compare: ensemble should be measurably wider with no phase collapse."""
    song_id, section_id, section = _check_renderable(db, song_id, section_id)
    queue = get_queue()

    jobs: dict[str, GenerationJob] = {}
    for mode in ("flat", "ensemble"):
        req = body.model_copy(update={"mode": mode})
        job = _queue_render(db, song_id, section_id, section, req)
        try:
            queue.wait(job.id, timeout=180)
        except TimeoutError as exc:
            raise HTTPException(504, f"{mode} render timed out") from exc
        db.refresh(job)
        if job.status != "succeeded":
            raise HTTPException(500, f"{mode} render failed: {job.error}")
        jobs[mode] = job

    ens = jobs["ensemble"].result_json.get("ab", {})
    flat = jobs["flat"].result_json.get("ab", {})
    verdict = {
        "wider": ens.get("width_ratio", 0) > flat.get("width_ratio", 0) + 0.01,
        "less_correlated": ens.get("stereo_correlation", 1)
        < flat.get("stereo_correlation", 1) - 0.02,
        "no_phase_collapse": ens.get("mono_compat", 0) > 0.5,
        "width_gain": round(ens.get("width_ratio", 0) - flat.get("width_ratio", 0), 4),
    }
    verdict["ensemble_clearly_different"] = bool(
        verdict["wider"] and verdict["less_correlated"] and verdict["no_phase_collapse"]
    )
    return ABResult(
        seed=jobs["ensemble"].seed,
        ensemble_job_id=jobs["ensemble"].id,
        flat_job_id=jobs["flat"].id,
        ensemble=ens,
        flat=flat,
        verdict=verdict,
    )


@router.get("/{song_id}/sections/{section_id}/renders", response_model=list[JobRead])
def list_section_renders(
    song_id: str, section_id: str, db: Session = Depends(get_db)
) -> list[GenerationJob]:
    _section(db, song_id, section_id)
    return list(
        db.scalars(
            select(GenerationJob)
            .options(selectinload(GenerationJob.outputs))
            .where(
                GenerationJob.section_id == section_id,
                GenerationJob.job_type == "render_section",
            )
            .order_by(GenerationJob.created_at.desc())
        )
    )


@router.get("/{song_id}/renders/{job_id}/takes", response_model=list[RenderTakeRead])
def list_render_takes(song_id: str, job_id: str, db: Session = Depends(get_db)) -> list[RenderTake]:
    job = db.get(GenerationJob, job_id)
    if job is None or job.song_id != song_id:
        raise HTTPException(404, "render job not found")
    return list(
        db.scalars(
            select(RenderTake)
            .where(RenderTake.generation_job_id == job_id)
            .order_by(RenderTake.vocal_role_id, RenderTake.singer_id, RenderTake.take_index)
        )
    )


@router.get("/{song_id}/assets/{asset_id}/download")
def download_asset(
    song_id: str, asset_id: str, inline: bool = Query(default=False), db: Session = Depends(get_db)
) -> FileResponse:
    _song(db, song_id)
    asset = db.get(AudioAsset, asset_id)
    if asset is None or asset.song_id != song_id:
        raise HTTPException(404, "asset not found")
    path = get_storage().path_for(asset.file_path)
    if not path.exists():
        raise HTTPException(410, "asset file is gone")
    disposition = "inline" if inline else "attachment"
    name = f"{(asset.label or asset.asset_type).replace(' ', '_')}{Path(asset.file_path).suffix}"
    return FileResponse(
        path, media_type="audio/wav", filename=name,
        content_disposition_type=disposition,
    )
