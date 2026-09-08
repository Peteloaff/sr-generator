"""Player style-model setup: training samples, train job, learned profile."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from sr.common import audio, playerstyle
from sr.common.storage import get_storage
from sr.db import get_db
from sr.models.audio_asset import AudioAsset
from sr.models.generation_job import GenerationJob
from sr.models.player import Player
from sr.schemas.audio import AudioAssetRead
from sr.schemas.job import JobRead
from sr.schemas.style_model import StyleModelRead, StyleProfileUpdate
from sr.services.consent import ConsentError, require_player_training
from sr.worker.queue import get_queue

router = APIRouter(prefix="/players", tags=["style-model"])


def _player(db: Session, player_id: str) -> Player:
    player = db.get(Player, player_id)
    if player is None:
        raise HTTPException(404, "player not found")
    return player


def _model_view(player: Player) -> StyleModelRead:
    return StyleModelRead(
        player_id=player.id,
        role=player.role,
        training_status=player.training_status,
        training_samples=player.training_samples,
        style_model_provider=player.style_model_provider,
        style_profile=player.style_profile_json,
    )


@router.get("/{player_id}/style-model", response_model=StyleModelRead)
def get_style_model(player_id: str, db: Session = Depends(get_db)) -> StyleModelRead:
    return _model_view(_player(db, player_id))


@router.get("/{player_id}/samples", response_model=list[AudioAssetRead])
def list_samples(player_id: str, db: Session = Depends(get_db)) -> list[AudioAsset]:
    _player(db, player_id)
    return list(
        db.scalars(
            select(AudioAsset).where(
                AudioAsset.player_id == player_id, AudioAsset.asset_type == "player_sample"
            )
        )
    )


@router.post("/{player_id}/samples", response_model=AudioAssetRead, status_code=201)
async def upload_sample(
    player_id: str, file: UploadFile = File(...), db: Session = Depends(get_db)
) -> AudioAsset:
    player = _player(db, player_id)
    count = len(list_samples(player_id, db))
    data = await file.read()
    base = f"models/players/{player.band_id}/{player_id}/sample_{count:03d}"
    try:
        ing = audio.ingest_upload(get_storage(), base, file.filename or "sample", data)
    except ValueError as exc:
        raise HTTPException(415 if "unsupported" in str(exc) else 422, str(exc)) from exc
    asset = AudioAsset(
        player_id=player_id, asset_type="player_sample", file_path=ing.original_key,
        label=f"{player.name} — training song {count + 1}",
        sample_rate=ing.info.sample_rate, channels=ing.info.channels, duration=ing.info.duration,
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)
    return asset


class DriveSamplesRequest(BaseModel):
    drive_folder: str
    recursive: bool = True


@router.post(
    "/{player_id}/samples/import-drive",
    response_model=list[AudioAssetRead],
    status_code=201,
)
def import_samples_from_drive(
    player_id: str, body: DriveSamplesRequest, db: Session = Depends(get_db)
) -> list[AudioAsset]:
    from sr.services import drive

    player = _player(db, player_id)
    try:
        folder_id = drive.parse_folder_id(body.drive_folder)
        listing = drive.list_folder_audio(folder_id, recursive=body.recursive)
    except drive.DriveError as exc:
        raise HTTPException(400, str(exc)) from exc
    if not listing:
        raise HTTPException(422, "no audio files in that Drive folder (is it link-shared?)")

    count = len(list_samples(player_id, db))
    made: list[AudioAsset] = []
    for f in listing:
        try:
            data = drive.download(f["id"])
            base = f"models/players/{player.band_id}/{player_id}/sample_{count:03d}"
            ing = audio.ingest_upload(get_storage(), base, f["name"], data)
        except (drive.DriveError, ValueError):
            continue
        asset = AudioAsset(
            player_id=player_id, asset_type="player_sample", file_path=ing.original_key,
            label=f"{player.name} — {f['name']} (Drive)",
            sample_rate=ing.info.sample_rate, channels=ing.info.channels,
            duration=ing.info.duration,
        )
        db.add(asset)
        made.append(asset)
        count += 1
    db.commit()
    for a in made:
        db.refresh(a)
    return made


@router.delete("/{player_id}/samples/{asset_id}", status_code=204)
def delete_sample(player_id: str, asset_id: str, db: Session = Depends(get_db)) -> None:
    asset = db.get(AudioAsset, asset_id)
    if asset is None or asset.player_id != player_id or asset.asset_type != "player_sample":
        raise HTTPException(404, "sample not found")
    db.delete(asset)
    db.commit()


@router.post("/{player_id}/style-model/train", response_model=JobRead, status_code=201)
def train_style_model(player_id: str, db: Session = Depends(get_db)) -> GenerationJob:
    player = _player(db, player_id)
    try:
        require_player_training(player)
    except ConsentError as exc:
        raise HTTPException(403, str(exc)) from exc
    if not list_samples(player_id, db):
        raise HTTPException(422, "upload at least one training song first")

    job = GenerationJob(
        job_type="train_player", provider="playerstyle", status="queued",
        parameters_json={"player_id": player_id},
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    get_queue().enqueue(job.id)
    db.refresh(job)
    return job


@router.patch("/{player_id}/style-model", response_model=StyleModelRead)
def set_style_profile(
    player_id: str, payload: StyleProfileUpdate, db: Session = Depends(get_db)
) -> StyleModelRead:
    player = _player(db, player_id)
    current = playerstyle.StyleProfile.from_dict(player.style_profile_json)
    merged = {**current.to_dict(), "role": player.role, **payload.model_dump(exclude_unset=True)}
    player.style_profile_json = playerstyle.StyleProfile.from_dict(merged).to_dict()
    if player.training_status in ("none", "failed"):
        player.training_status = "ready"
    if not player.style_model_provider:
        player.style_model_provider = "manual"
    db.commit()
    db.refresh(player)
    return _model_view(player)
