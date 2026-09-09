"""Singer voice-model setup: training samples, train job, profile."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from sr.api.deps import get_band
from sr.common import audio, voice
from sr.common.storage import get_storage
from sr.db import get_db
from sr.models.audio_asset import AudioAsset
from sr.models.band import Band
from sr.models.generation_job import GenerationJob
from sr.models.singer import Singer
from sr.schemas.audio import AudioAssetRead
from sr.schemas.job import JobRead
from sr.schemas.voice_model import VoiceModelRead, VoiceProfileUpdate
from sr.services.consent import ConsentError, require_training
from sr.worker.queue import get_queue

router = APIRouter(prefix="/singers", tags=["voice-model"])


def _singer(db: Session, singer_id: str) -> Singer:
    singer = db.get(Singer, singer_id)
    if singer is None:
        raise HTTPException(404, "singer not found")
    return singer


def _model_view(singer: Singer) -> VoiceModelRead:
    return VoiceModelRead(
        singer_id=singer.id,
        training_status=singer.training_status,
        training_samples=singer.training_samples,
        voice_model_provider=singer.voice_model_provider,
        voice_profile=singer.voice_profile_json,
    )


@router.get("/{singer_id}/voice-model", response_model=VoiceModelRead)
def get_voice_model(singer_id: str, db: Session = Depends(get_db)) -> VoiceModelRead:
    return _model_view(_singer(db, singer_id))


_SAMPLE_TYPES = ("singer_sample", "singer_song")


@router.get("/{singer_id}/samples", response_model=list[AudioAssetRead])
def list_samples(singer_id: str, db: Session = Depends(get_db)) -> list[AudioAsset]:
    _singer(db, singer_id)
    return list(
        db.scalars(
            select(AudioAsset).where(
                AudioAsset.singer_id == singer_id,
                AudioAsset.asset_type.in_(_SAMPLE_TYPES),
            )
        )
    )


def _store_sample(
    db: Session, singer: Singer, filename: str, data: bytes, *, full_song: bool
) -> AudioAsset:
    count = len(list_samples(singer.id, db))
    base = f"models/singers/{singer.band_id}/{singer.id}/sample_{count:03d}"
    try:
        ing = audio.ingest_upload(get_storage(), base, filename or "sample", data)
    except ValueError as exc:
        raise HTTPException(415 if "unsupported" in str(exc) else 422, str(exc)) from exc
    kind = "singer_song" if full_song else "singer_sample"
    asset = AudioAsset(
        singer_id=singer.id, asset_type=kind, file_path=ing.original_key,
        label=f"{singer.name} — " + ("full song" if full_song else "vocal clip") + f" {count + 1}",
        sample_rate=ing.info.sample_rate, channels=ing.info.channels, duration=ing.info.duration,
    )
    db.add(asset)
    return asset


@router.post("/{singer_id}/samples", response_model=AudioAssetRead, status_code=201)
async def upload_sample(
    singer_id: str,
    file: UploadFile = File(...),
    full_song: bool = Form(default=False),
    db: Session = Depends(get_db),
) -> AudioAsset:
    singer = _singer(db, singer_id)
    asset = _store_sample(
        db, singer, file.filename or "sample", await file.read(), full_song=full_song
    )
    db.commit()
    db.refresh(asset)
    return asset


@router.post("/from-song", response_model=JobRead, status_code=201)
async def create_singer_from_song(
    file: UploadFile = File(...),
    name: str = Form(...),
    band: Band = Depends(get_band),
    db: Session = Depends(get_db),
) -> GenerationJob:
    """One shot: upload a song, separate the vocal, and train a new singer from it."""
    if db.scalar(select(Singer).where(Singer.band_id == band.id, Singer.name == name.strip())):
        raise HTTPException(409, f"a singer named {name.strip()!r} already exists in this band")
    singer = Singer(
        band_id=band.id, name=name.strip(),
        consent_training=True, consent_generation=True,
    )
    db.add(singer)
    db.flush()
    _store_sample(db, singer, file.filename or "song", await file.read(), full_song=True)
    job = GenerationJob(
        job_type="train_singer", provider="voice", status="queued",
        parameters_json={"singer_id": singer.id},
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    get_queue().enqueue(job.id)
    db.refresh(job)
    return job


@router.delete("/{singer_id}/samples/{asset_id}", status_code=204)
def delete_sample(singer_id: str, asset_id: str, db: Session = Depends(get_db)) -> None:
    asset = db.get(AudioAsset, asset_id)
    if asset is None or asset.singer_id != singer_id or asset.asset_type not in _SAMPLE_TYPES:
        raise HTTPException(404, "sample not found")
    db.delete(asset)
    db.commit()


@router.post("/{singer_id}/voice-model/train", response_model=JobRead, status_code=201)
def train_voice_model(singer_id: str, db: Session = Depends(get_db)) -> GenerationJob:
    singer = _singer(db, singer_id)
    try:
        require_training(singer)
    except ConsentError as exc:
        raise HTTPException(403, str(exc)) from exc
    if not list_samples(singer_id, db):
        raise HTTPException(422, "upload at least one training sample first")

    job = GenerationJob(
        job_type="train_singer", provider="voice", status="queued",
        parameters_json={"singer_id": singer_id},
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    get_queue().enqueue(job.id)
    db.refresh(job)
    return job


@router.patch("/{singer_id}/voice-model", response_model=VoiceModelRead)
def set_voice_profile(
    singer_id: str, payload: VoiceProfileUpdate, db: Session = Depends(get_db)
) -> VoiceModelRead:
    singer = _singer(db, singer_id)
    current = voice.VoiceProfile.from_dict(singer.voice_profile_json).to_dict()
    current.update(payload.model_dump(exclude_unset=True))
    singer.voice_profile_json = current
    if singer.training_status in ("none", "failed"):
        singer.training_status = "ready"
    if not singer.voice_model_provider:
        singer.voice_model_provider = "manual"
    db.commit()
    db.refresh(singer)
    return _model_view(singer)
