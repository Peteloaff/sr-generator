from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from sr.common.resolver import resolve_line_roles
from sr.db import get_db
from sr.models.song import LyricLine, Song, SongSection
from sr.schemas.song import (
    LyricLineCreate,
    LyricLineRead,
    SectionCreate,
    SectionRead,
    SongCreate,
    SongRead,
    SongUpdate,
)

router = APIRouter(prefix="/songs", tags=["songs"])


def _get_song(db: Session, song_id: str) -> Song:
    song = db.get(Song, song_id)
    if song is None:
        raise HTTPException(404, "song not found")
    return song


@router.get("", response_model=list[SongRead])
def list_songs(db: Session = Depends(get_db)) -> list[Song]:
    return list(db.scalars(select(Song).order_by(Song.created_at)))


@router.post("", response_model=SongRead, status_code=201)
def create_song(payload: SongCreate, db: Session = Depends(get_db)) -> Song:
    song = Song(**payload.model_dump())
    db.add(song)
    db.commit()
    db.refresh(song)
    return song


@router.get("/{song_id}", response_model=SongRead)
def get_song(song_id: str, db: Session = Depends(get_db)) -> Song:
    return _get_song(db, song_id)


@router.patch("/{song_id}", response_model=SongRead)
def update_song(song_id: str, payload: SongUpdate, db: Session = Depends(get_db)) -> Song:
    song = _get_song(db, song_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(song, field, value.value if hasattr(value, "value") else value)
    db.commit()
    db.refresh(song)
    return song


@router.delete("/{song_id}", status_code=204)
def delete_song(song_id: str, db: Session = Depends(get_db)) -> None:
    db.delete(_get_song(db, song_id))
    db.commit()


# --- sections -------------------------------------------------------------

@router.get("/{song_id}/sections", response_model=list[SectionRead])
def list_sections(song_id: str, db: Session = Depends(get_db)) -> list[SongSection]:
    _get_song(db, song_id)
    return list(
        db.scalars(
            select(SongSection)
            .where(SongSection.song_id == song_id)
            .order_by(SongSection.order_index)
        )
    )


@router.post("/{song_id}/sections", response_model=SectionRead, status_code=201)
def create_section(
    song_id: str, payload: SectionCreate, db: Session = Depends(get_db)
) -> SongSection:
    _get_song(db, song_id)
    section = SongSection(song_id=song_id, **payload.model_dump(mode="json"))
    db.add(section)
    db.commit()
    db.refresh(section)
    return section


@router.delete("/{song_id}/sections/{section_id}", status_code=204)
def delete_section(song_id: str, section_id: str, db: Session = Depends(get_db)) -> None:
    section = db.get(SongSection, section_id)
    if section is None or section.song_id != song_id:
        raise HTTPException(404, "section not found")
    db.delete(section)
    db.commit()


# --- lyric lines --------------------------------------------------------

@router.get("/{song_id}/lines", response_model=list[LyricLineRead])
def list_lines(song_id: str, db: Session = Depends(get_db)) -> list[LyricLine]:
    _get_song(db, song_id)
    return list(
        db.scalars(
            select(LyricLine)
            .where(LyricLine.song_id == song_id)
            .order_by(LyricLine.order_index)
        )
    )


@router.post("/{song_id}/lines", response_model=LyricLineRead, status_code=201)
def create_line(
    song_id: str, payload: LyricLineCreate, db: Session = Depends(get_db)
) -> LyricLine:
    _get_song(db, song_id)
    if payload.section_id is not None:
        section = db.get(SongSection, payload.section_id)
        if section is None or section.song_id != song_id:
            raise HTTPException(422, "section_id does not belong to this song")
    line = LyricLine(song_id=song_id, **payload.model_dump())
    db.add(line)
    db.commit()
    db.refresh(line)
    return line


@router.delete("/{song_id}/lines/{line_id}", status_code=204)
def delete_line(song_id: str, line_id: str, db: Session = Depends(get_db)) -> None:
    line = db.get(LyricLine, line_id)
    if line is None or line.song_id != song_id:
        raise HTTPException(404, "line not found")
    db.delete(line)
    db.commit()


@router.get("/{song_id}/lines/{line_id}/resolved-roles")
def get_resolved_roles(song_id: str, line_id: str, db: Session = Depends(get_db)) -> dict:
    line = db.get(LyricLine, line_id)
    if line is None or line.song_id != song_id:
        raise HTTPException(404, "line not found")
    resolved = resolve_line_roles(line)
    return {
        "line_id": resolved.line_id,
        "source": resolved.source,
        "roles": [
            {
                "id": r.id,
                "role_type": r.role_type,
                "ensemble_size": r.ensemble_size,
                "assignments": [
                    {"singer_id": a.singer_id, "weight_percent": a.weight_percent}
                    for a in r.assignments
                ],
            }
            for r in resolved.roles
        ],
    }
