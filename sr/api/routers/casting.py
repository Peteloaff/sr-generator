"""Instrument casting: which player performs which instrument, per song/section."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from sr.db import get_db
from sr.models.instrument_slot import InstrumentSlot
from sr.models.player import Player
from sr.models.song import Song, SongSection
from sr.schemas.casting import InstrumentSlotRead, InstrumentSlotWrite

router = APIRouter(prefix="/songs", tags=["casting"])


def _song(db: Session, song_id: str) -> Song:
    song = db.get(Song, song_id)
    if song is None:
        raise HTTPException(404, "song not found")
    return song


@router.get("/{song_id}/instruments", response_model=list[InstrumentSlotRead])
def list_instruments(song_id: str, db: Session = Depends(get_db)) -> list[InstrumentSlot]:
    _song(db, song_id)
    return list(
        db.scalars(
            select(InstrumentSlot)
            .where(InstrumentSlot.song_id == song_id)
            .order_by(InstrumentSlot.section_id.is_(None).desc(), InstrumentSlot.role)
        )
    )


@router.put("/{song_id}/instruments", response_model=InstrumentSlotRead)
def set_instrument(
    song_id: str, payload: InstrumentSlotWrite, db: Session = Depends(get_db)
) -> InstrumentSlot:
    song = _song(db, song_id)
    role = payload.role.value

    if payload.section_id is not None:
        sec = db.get(SongSection, payload.section_id)
        if sec is None or sec.song_id != song_id:
            raise HTTPException(404, "section not found in this song")
    if payload.player_id is not None:
        player = db.get(Player, payload.player_id)
        if player is None or player.band_id != song.band_id:
            raise HTTPException(404, "player not found in this band")
        if player.role != role:
            raise HTTPException(422, f"player {player.name!r} is a {player.role}, not {role}")

    slot = db.scalar(
        select(InstrumentSlot).where(
            InstrumentSlot.song_id == song_id,
            InstrumentSlot.role == role,
            InstrumentSlot.section_id.is_(payload.section_id)
            if payload.section_id is None
            else InstrumentSlot.section_id == payload.section_id,
        )
    )
    dials = payload.dials.model_dump(exclude_none=True) if payload.dials else None
    if slot is None:
        slot = InstrumentSlot(song_id=song_id, role=role, section_id=payload.section_id)
        db.add(slot)
    slot.player_id = payload.player_id
    slot.muted = payload.muted
    slot.gain_db = payload.gain_db
    slot.explore = payload.explore
    slot.dials_json = dials or None
    db.commit()
    db.refresh(slot)
    return slot


@router.delete("/{song_id}/instruments/{slot_id}", status_code=204)
def clear_instrument(song_id: str, slot_id: str, db: Session = Depends(get_db)) -> None:
    slot = db.get(InstrumentSlot, slot_id)
    if slot is None or slot.song_id != song_id:
        raise HTTPException(404, "slot not found")
    db.delete(slot)
    db.commit()
