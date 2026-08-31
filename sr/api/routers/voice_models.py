"""Singer voice-model setup: training samples, train job, profile."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from sr.common import audio, voice
from sr.common.storage import get_storage
from sr.db import get_db
from sr.models.audio_asset import AudioAsset
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


@router.get("/{singer_id}/samples", response_model=list[AudioAssetRead])
def list_samples(singer_id: str, db: Session = Depends(get_db)) -> list[AudioAsset]:
    _singer(db, singer_id)
    return list(
        db.scalars(
            select(AudioAsset).where(
                AudioAsset.singer_id == singer_id, AudioAsset.asset_type == "singer_sample"
            )
        )
    )


@router.post("/{singer_id}/samples", response_model=AudioAssetRead, status_code=201)
async def upload_sample(
    singer_id: str, file: UploadFile = File(...), db: Session = Depends(get_db)
) -> AudioAsset:
    singer = _singer(db, singer_id)
    count = len(list_samples(singer_id, db))
    data = await file.read()
    base = f"models/singers/{singer.band_id}/{singer_id}/sample_{count:03d}"
    try:
        ing = audio.ingest_upload(get_storage(), base, file.filename or "sample", data)
    except ValueError as exc:
        raise HTTPException(415 if "unsupported" in str(exc) else 422, str(exc)) from exc
    asset = AudioAsset(
        singer_id=singer_id, asset_type="singer_sample", file_path=ing.original_key,
        label=f"{singer.name} — training sample {count + 1}",
        sample_rate=ing.info.sample_rate, channels=ing.info.channels, duration=ing.info.duration,
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)
    return asset


@router.delete("/{singer_id}/samples/{asset_id}", status_code=204)
def delete_sample(singer_id: str, asset_id: str, db: Session = Depends(get_db)) -> None:
    asset = db.get(AudioAsset, asset_id)
    if asset is None or asset.singer_id != singer_id or asset.asset_type != "singer_sample":
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
