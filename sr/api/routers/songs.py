from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from sr.api.deps import get_band
from sr.common import audio
from sr.common.resolver import resolve_line_roles
from sr.common.storage import get_storage
from sr.db import get_db
from sr.models.audio_asset import AudioAsset
from sr.models.band import Band
from sr.models.song import LyricLine, Song, SongSection
from sr.schemas.audio import AudioAssetRead, WaveformRead
from sr.schemas.song import (
    LyricLineCreate,
    LyricLineRead,
    LyricLineUpdate,
    LyricsReplace,
    SectionCreate,
    SectionRead,
    SectionUpdate,
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


def _section_of_song(db: Session, song_id: str, section_id: str) -> SongSection:
    section = db.get(SongSection, section_id)
    if section is None or section.song_id != song_id:
        raise HTTPException(404, "section not found")
    return section


def _line_of_song(db: Session, song_id: str, line_id: str) -> LyricLine:
    line = db.get(LyricLine, line_id)
    if line is None or line.song_id != song_id:
        raise HTTPException(404, "line not found")
    return line


# --- songs -------------------------------------------------------------

@router.get("", response_model=list[SongRead])
def list_songs(band: Band = Depends(get_band), db: Session = Depends(get_db)) -> list[Song]:
    return list(
        db.scalars(select(Song).where(Song.band_id == band.id).order_by(Song.created_at))
    )


@router.post("", response_model=SongRead, status_code=201)
def create_song(
    payload: SongCreate, band: Band = Depends(get_band), db: Session = Depends(get_db)
) -> Song:
    song = Song(band_id=band.id, **payload.model_dump())
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


# --- audio upload + waveform -----------------------------------------

@router.get("/{song_id}/assets", response_model=list[AudioAssetRead])
def list_song_assets(song_id: str, db: Session = Depends(get_db)) -> list[AudioAsset]:
    _get_song(db, song_id)
    return list(
        db.scalars(
            select(AudioAsset).where(AudioAsset.song_id == song_id).order_by(AudioAsset.created_at)
        )
    )


@router.post("/{song_id}/audio", response_model=AudioAssetRead, status_code=201)
async def upload_song_audio(
    song_id: str, file: UploadFile = File(...), db: Session = Depends(get_db)
) -> AudioAsset:
    song = _get_song(db, song_id)
    data = await file.read()
    try:
        ing = audio.ingest_upload(
            get_storage(), f"references/{song.band_id}/{song_id}", file.filename or "upload", data
        )
    except ValueError as exc:
        raise HTTPException(415 if "unsupported" in str(exc) else 422, str(exc)) from exc

    asset = AudioAsset(
        song_id=song_id,
        asset_type="upload",
        file_path=ing.original_key,
        sample_rate=ing.info.sample_rate,
        channels=ing.info.channels,
        duration=ing.info.duration,
    )
    db.add(asset)
    if song.duration is None:
        song.duration = ing.info.duration
    db.commit()
    db.refresh(asset)
    return asset


@router.get("/{song_id}/assets/{asset_id}/waveform", response_model=WaveformRead)
def get_waveform(song_id: str, asset_id: str, db: Session = Depends(get_db)) -> WaveformRead:
    _get_song(db, song_id)
    asset = db.get(AudioAsset, asset_id)
    if asset is None or asset.song_id != song_id:
        raise HTTPException(404, "asset not found")
    storage = get_storage()
    base = str(Path(asset.file_path).parent)
    peaks_key = f"{base}/peaks.json"
    if storage.exists(peaks_key):
        peaks = json.loads(storage.read_bytes(peaks_key))
    else:
        canonical = storage.path_for(f"{base}/canonical.wav")
        if not canonical.exists():
            audio.to_canonical_wav(storage.path_for(asset.file_path), canonical)
        peaks = audio.waveform_peaks(canonical)
        storage.write_text(peaks_key, json.dumps(peaks))
    return WaveformRead(
        asset_id=asset_id, buckets=len(peaks), duration=asset.duration, peaks=peaks
    )


# --- sections --------------------------------------------------------

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


@router.patch("/{song_id}/sections/{section_id}", response_model=SectionRead)
def update_section(
    song_id: str, section_id: str, payload: SectionUpdate, db: Session = Depends(get_db)
) -> SongSection:
    section = _section_of_song(db, song_id, section_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(section, field, value.value if hasattr(value, "value") else value)
    db.commit()
    db.refresh(section)
    return section


@router.put("/{song_id}/sections/reorder", response_model=list[SectionRead])
def reorder_sections(
    song_id: str, ordered_ids: list[str], db: Session = Depends(get_db)
) -> list[SongSection]:
    _get_song(db, song_id)
    sections = {
        s.id: s
        for s in db.scalars(select(SongSection).where(SongSection.song_id == song_id))
    }
    if set(ordered_ids) != set(sections):
        raise HTTPException(422, "ordered_ids must be exactly this song's section ids")
    for i, sid in enumerate(ordered_ids):
        sections[sid].order_index = i
    db.commit()
    return list_sections(song_id, db)


@router.delete("/{song_id}/sections/{section_id}", status_code=204)
def delete_section(song_id: str, section_id: str, db: Session = Depends(get_db)) -> None:
    db.delete(_section_of_song(db, song_id, section_id))
    db.commit()


# --- lyric lines ----------------------------------------------------

@router.get("/{song_id}/lines", response_model=list[LyricLineRead])
def list_lines(song_id: str, db: Session = Depends(get_db)) -> list[LyricLine]:
    _get_song(db, song_id)
    return list(
        db.scalars(
            select(LyricLine).where(LyricLine.song_id == song_id).order_by(LyricLine.order_index)
        )
    )


@router.post("/{song_id}/lines", response_model=LyricLineRead, status_code=201)
def create_line(
    song_id: str, payload: LyricLineCreate, db: Session = Depends(get_db)
) -> LyricLine:
    _get_song(db, song_id)
    if payload.section_id is not None:
        _section_of_song(db, song_id, payload.section_id)
    line = LyricLine(song_id=song_id, **payload.model_dump())
    db.add(line)
    db.commit()
    db.refresh(line)
    return line


@router.put("/{song_id}/lines", response_model=list[LyricLineRead])
def replace_lines(
    song_id: str, payload: LyricsReplace, db: Session = Depends(get_db)
) -> list[LyricLine]:
    """Rebuild all lyric lines from a text block (one line each). Existing lines
    and their per-line vocal roles are dropped."""
    _get_song(db, song_id)
    if payload.section_id is not None:
        _section_of_song(db, song_id, payload.section_id)
    for old in db.scalars(select(LyricLine).where(LyricLine.song_id == song_id)):
        db.delete(old)
    db.flush()
    for i, text in enumerate(payload.text.splitlines()):
        db.add(
            LyricLine(
                song_id=song_id, section_id=payload.section_id, order_index=i, text=text
            )
        )
    db.commit()
    return list_lines(song_id, db)


@router.patch("/{song_id}/lines/{line_id}", response_model=LyricLineRead)
def update_line(
    song_id: str, line_id: str, payload: LyricLineUpdate, db: Session = Depends(get_db)
) -> LyricLine:
    line = _line_of_song(db, song_id, line_id)
    fields = payload.model_dump(exclude_unset=True)
    if fields.get("section_id") is not None:
        _section_of_song(db, song_id, fields["section_id"])
    for field, value in fields.items():
        setattr(line, field, value)
    db.commit()
    db.refresh(line)
    return line


@router.delete("/{song_id}/lines/{line_id}", status_code=204)
def delete_line(song_id: str, line_id: str, db: Session = Depends(get_db)) -> None:
    db.delete(_line_of_song(db, song_id, line_id))
    db.commit()


@router.get("/{song_id}/lines/{line_id}/resolved-roles")
def get_resolved_roles(song_id: str, line_id: str, db: Session = Depends(get_db)) -> dict:
    line = _line_of_song(db, song_id, line_id)
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
