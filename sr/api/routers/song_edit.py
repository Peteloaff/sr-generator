"""Stage 5 - stem separation, use-derived-stems, full-song assembly."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from sr.common import dsp
from sr.common.storage import get_storage
from sr.db import get_db
from sr.models.audio_asset import AudioAsset
from sr.models.generation_job import GenerationJob
from sr.models.song import Song, SongSection
from sr.schemas.audio import AudioAssetRead
from sr.schemas.job import JobRead
from sr.worker.queue import get_queue

router = APIRouter(prefix="/songs", tags=["song-edit"])

_SONG_STEMS = (
    "stem_lead_vocal", "stem_instrumental", "stem_drums", "stem_bass",
    "stem_guitars", "stem_synths", "stem_background_vocal",
)


def _song(db: Session, song_id: str) -> Song:
    song = db.get(Song, song_id)
    if song is None:
        raise HTTPException(404, "song not found")
    return song


def _latest_song_stem(db: Session, song_id: str, asset_type: str) -> AudioAsset | None:
    return db.scalar(
        select(AudioAsset)
        .where(
            AudioAsset.song_id == song_id,
            AudioAsset.section_id.is_(None),
            AudioAsset.asset_type == asset_type,
        )
        .order_by(AudioAsset.version.desc(), AudioAsset.created_at.desc())
    )


@router.post("/{song_id}/separate", response_model=JobRead, status_code=201)
def separate_stems(song_id: str, db: Session = Depends(get_db)) -> GenerationJob:
    _song(db, song_id)
    if db.scalar(
        select(AudioAsset).where(
            AudioAsset.song_id == song_id, AudioAsset.asset_type == "upload"
        )
    ) is None:
        raise HTTPException(422, "upload a mix first (POST /songs/{id}/audio)")
    job = GenerationJob(
        job_type="separate_stems", song_id=song_id, provider="stem", status="queued",
        parameters_json={},
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    get_queue().enqueue(job.id)
    db.refresh(job)
    return job


@router.get("/{song_id}/stems", response_model=list[AudioAssetRead])
def list_song_stems(song_id: str, db: Session = Depends(get_db)) -> list[AudioAsset]:
    _song(db, song_id)
    return list(
        db.scalars(
            select(AudioAsset)
            .where(
                AudioAsset.song_id == song_id,
                AudioAsset.section_id.is_(None),
                AudioAsset.asset_type.in_(_SONG_STEMS),
            )
            .order_by(AudioAsset.asset_type, AudioAsset.version.desc())
        )
    )


@router.post(
    "/{song_id}/sections/{section_id}/use-derived-stems",
    response_model=list[AudioAssetRead],
    status_code=201,
)
def use_derived_stems(
    song_id: str, section_id: str, db: Session = Depends(get_db)
) -> list[AudioAsset]:
    """Slice the song's separated vocal + instrumental to this section and wire
    them in as the section's guide vocal + instrumental bed."""
    _song(db, song_id)
    section = db.get(SongSection, section_id)
    if section is None or section.song_id != song_id:
        raise HTTPException(404, "section not found")
    if section.start_time is None or section.end_time is None:
        raise HTTPException(422, "section needs start_time and end_time")

    storage = get_storage()
    made: list[AudioAsset] = []
    plan = [("stem_lead_vocal", "guide_vocal", "guide"),
            ("stem_instrumental", "instrumental_bed", "instrumental")]
    for stem_type, section_type, folder in plan:
        src = _latest_song_stem(db, song_id, stem_type)
        if src is None:
            continue
        full = dsp.load_stereo(storage.path_for(src.file_path))
        s = int(section.start_time * dsp.SR)
        e = int(section.end_time * dsp.SR)
        clip = dsp.fit_length(full[s:e], max(1, e - s))

        for old in db.scalars(
            select(AudioAsset).where(
                AudioAsset.section_id == section_id, AudioAsset.asset_type == section_type
            )
        ):
            db.delete(old)
        db.flush()

        key = f"references/{section.song.band_id}/{song_id}/{section_id}/{folder}/canonical.wav"
        dsp.save_wav(storage.path_for(key), clip, dsp.SR)
        asset = AudioAsset(
            song_id=song_id, section_id=section_id, asset_type=section_type,
            file_path=key, parent_asset_id=src.id, sample_rate=dsp.SR, channels=2,
            duration=round(clip.shape[0] / dsp.SR, 3),
            label=f"{section_type.replace('_', ' ')} from separated {stem_type}",
        )
        db.add(asset)
        made.append(asset)

    if not made:
        raise HTTPException(422, "no separated stems yet - run POST /songs/{id}/separate")
    db.commit()
    for a in made:
        db.refresh(a)
    return made


@router.post("/{song_id}/assemble", response_model=JobRead, status_code=201)
def assemble_song(song_id: str, db: Session = Depends(get_db)) -> GenerationJob:
    _song(db, song_id)
    job = GenerationJob(
        job_type="assemble_song", song_id=song_id, provider="assembly-engine",
        status="queued", parameters_json={},
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    get_queue().enqueue(job.id)
    db.refresh(job)
    return job


@router.get("/{song_id}/mixes", response_model=list[AudioAssetRead])
def list_song_mixes(song_id: str, db: Session = Depends(get_db)) -> list[AudioAsset]:
    _song(db, song_id)
    return list(
        db.scalars(
            select(AudioAsset)
            .where(AudioAsset.song_id == song_id, AudioAsset.asset_type == "song_mix")
            .order_by(AudioAsset.version.desc())
        )
    )


@router.get("/{song_id}/edit-jobs", response_model=list[JobRead])
def list_edit_jobs(song_id: str, db: Session = Depends(get_db)) -> list[GenerationJob]:
    _song(db, song_id)
    return list(
        db.scalars(
            select(GenerationJob)
            .options(selectinload(GenerationJob.outputs))
            .where(
                GenerationJob.song_id == song_id,
                GenerationJob.job_type.in_(("separate_stems", "assemble_song")),
            )
            .order_by(GenerationJob.created_at.desc())
        )
    )
