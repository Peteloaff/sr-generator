from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from sr.api.deps import get_band
from sr.common import player_presets
from sr.db import get_db
from sr.models.band import Band
from sr.models.enums import PlayerRole
from sr.models.player import Player
from sr.schemas.player import (
    ApplyPresetRequest,
    PlayerCreate,
    PlayerFromPreset,
    PlayerRead,
    PlayerUpdate,
)

router = APIRouter(prefix="/players", tags=["players"])


def _player(db: Session, player_id: str) -> Player:
    player = db.get(Player, player_id)
    if player is None:
        raise HTTPException(404, "player not found")
    return player


@router.get("/presets")
def list_style_presets(role: PlayerRole | None = Query(default=None)) -> list[dict]:
    return player_presets.list_presets(role.value if role else None)


@router.post("/from-preset", response_model=PlayerRead, status_code=201)
def create_player_from_preset(
    payload: PlayerFromPreset, band: Band = Depends(get_band), db: Session = Depends(get_db)
) -> Player:
    preset = player_presets.get_preset(payload.preset)
    if preset is None:
        raise HTTPException(404, f"unknown style preset {payload.preset!r}")
    band_id = payload.band_id or band.id
    if db.scalar(
        select(Player).where(Player.band_id == band_id, Player.name == payload.name)
    ):
        raise HTTPException(409, f"player named {payload.name!r} already exists in this band")
    player = Player(
        band_id=band_id, name=payload.name, role=preset["role"],
        style_profile_json=preset["profile"], style_model_provider="preset",
        style_model_path_or_id=preset["id"], training_status="ready",
        consent_training=True, consent_generation=True,
        notes=f"Signature style: {preset['label']}",
    )
    db.add(player)
    db.commit()
    db.refresh(player)
    return player


@router.get("", response_model=list[PlayerRead])
def list_players(
    role: PlayerRole | None = Query(default=None),
    band: Band = Depends(get_band),
    db: Session = Depends(get_db),
) -> list[Player]:
    stmt = select(Player).where(Player.band_id == band.id)
    if role is not None:
        stmt = stmt.where(Player.role == role.value)
    return list(db.scalars(stmt.order_by(Player.role, Player.name)))


@router.post("", response_model=PlayerRead, status_code=201)
def create_player(
    payload: PlayerCreate, band: Band = Depends(get_band), db: Session = Depends(get_db)
) -> Player:
    band_id = payload.band_id or band.id
    if db.get(Band, band_id) is None:
        raise HTTPException(404, f"band {band_id!r} not found")
    if db.scalar(
        select(Player).where(Player.band_id == band_id, Player.name == payload.name)
    ):
        raise HTTPException(409, f"player named {payload.name!r} already exists in this band")
    data = payload.model_dump(exclude={"band_id"})
    data["role"] = data["role"].value if hasattr(data["role"], "value") else data["role"]
    player = Player(band_id=band_id, **data)
    db.add(player)
    db.commit()
    db.refresh(player)
    return player


@router.get("/{player_id}", response_model=PlayerRead)
def get_player(player_id: str, db: Session = Depends(get_db)) -> Player:
    return _player(db, player_id)


@router.patch("/{player_id}", response_model=PlayerRead)
def update_player(player_id: str, payload: PlayerUpdate, db: Session = Depends(get_db)) -> Player:
    player = _player(db, player_id)
    updates = payload.model_dump(exclude_unset=True)
    if "name" in updates and updates["name"] != player.name and db.scalar(
        select(Player).where(
            Player.band_id == player.band_id, Player.name == updates["name"]
        )
    ):
        raise HTTPException(409, f"player named {updates['name']!r} already exists in this band")
    for field, value in updates.items():
        setattr(player, field, value.value if hasattr(value, "value") else value)
    db.commit()
    db.refresh(player)
    return player


@router.post("/{player_id}/apply-preset", response_model=PlayerRead)
def apply_style_preset(
    player_id: str, payload: ApplyPresetRequest, db: Session = Depends(get_db)
) -> Player:
    player = _player(db, player_id)
    preset = player_presets.get_preset(payload.preset)
    if preset is None:
        raise HTTPException(404, f"unknown style preset {payload.preset!r}")
    if preset["role"] != player.role:
        raise HTTPException(
            422, f"{preset['label']!r} is a {preset['role']} style, not {player.role}"
        )
    player.style_profile_json = preset["profile"]
    player.style_model_provider = "preset"
    player.style_model_path_or_id = preset["id"]
    if player.training_status in ("none", "failed"):
        player.training_status = "ready"
    db.commit()
    db.refresh(player)
    return player


@router.delete("/{player_id}", status_code=204)
def delete_player(player_id: str, db: Session = Depends(get_db)) -> None:
    db.delete(_player(db, player_id))
    db.commit()
