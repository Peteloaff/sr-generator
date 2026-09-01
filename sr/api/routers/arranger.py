"""Stage 10 - intelligent vocal arranger: recommend + apply."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from sr.db import get_db
from sr.models.song import Song
from sr.schemas.compose import ArrangementApplyRequest
from sr.services import arranger as arranger_svc

router = APIRouter(prefix="/songs", tags=["arranger"])


def _song(db: Session, song_id: str) -> Song:
    song = db.get(Song, song_id)
    if song is None:
        raise HTTPException(404, "song not found")
    return song


@router.get("/{song_id}/arrangement/recommend")
def recommend(
    song_id: str, seed: int = Query(default=0), db: Session = Depends(get_db)
) -> dict:
    song = _song(db, song_id)
    return arranger_svc.recommend_arrangement(db, song, seed=seed or song.seed or 0)


@router.post("/{song_id}/arrangement/apply")
def apply(
    song_id: str, body: ArrangementApplyRequest, db: Session = Depends(get_db)
) -> dict:
    song = _song(db, song_id)
    return arranger_svc.apply_arrangement(
        db, song,
        section_ids=body.section_ids,
        overwrite=body.overwrite,
        seed=body.seed if body.seed is not None else (song.seed or 0),
    )
