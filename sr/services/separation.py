"""Separate a song's uploaded mix into song-level stems (versioned)."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from sr.common.storage import get_storage
from sr.models.audio_asset import AudioAsset
from sr.models.generation_job import GenerationJob
from sr.models.song import Song
from sr.providers.base import ProviderResult
from sr.providers.registry import get_provider
from sr.worker.progress import report as report_progress


def _canonical_key(asset: AudioAsset) -> str:
    return f"{Path(asset.file_path).parent}/canonical.wav"


def separate_song(
    db: Session, job: GenerationJob, *, song_id: str, params: dict
) -> ProviderResult:
    song = db.get(Song, song_id)
    if song is None:
        raise LookupError(f"song {song_id} not found")
    upload = db.scalar(
        select(AudioAsset)
        .where(AudioAsset.song_id == song_id, AudioAsset.asset_type == "upload")
        .order_by(AudioAsset.created_at.desc())
    )
    if upload is None:
        raise ValueError("song has no uploaded mix to separate")
    storage = get_storage()
    source_key = _canonical_key(upload)
    if not storage.exists(source_key):
        raise ValueError("uploaded mix canonical WAV is missing")

    report_progress(db, job, 0.1, "separating")
    provider = get_provider("stem")
    sep = provider.separate(source_path=storage.ensure_local(source_key), params=params)

    base_key = f"stems/{song_id[:8]}/{job.id[:8]}"
    made: list[dict] = []
    for i, (stem_type, arr) in enumerate(sorted(sep.stems.items())):
        prior = db.scalar(
            select(AudioAsset)
            .where(
                AudioAsset.song_id == song_id,
                AudioAsset.section_id.is_(None),
                AudioAsset.asset_type == stem_type,
            )
            .order_by(AudioAsset.version.desc())
        )
        version = (prior.version + 1) if prior else 1
        key = f"{base_key}/{stem_type}_v{version}.wav"
        stereo = arr if arr.ndim == 2 else arr.reshape(-1, 1).repeat(2, axis=1)
        storage.save_wav(key, stereo, sep.sample_rate)
        db.add(
            AudioAsset(
                song_id=song_id, generation_job_id=job.id, parent_asset_id=upload.id,
                asset_type=stem_type, file_path=key, version=version,
                sample_rate=sep.sample_rate, channels=2,
                duration=round(stereo.shape[0] / sep.sample_rate, 3),
                label=f"{stem_type.replace('_', ' ')} v{version} ({sep.provider})",
            )
        )
        made.append({"asset_type": stem_type, "version": version})
        report_progress(db, job, 0.3 + 0.6 * (i + 1) / len(sep.stems), f"wrote {stem_type}")

    db.flush()
    return ProviderResult(
        provider=sep.provider,
        provider_version=sep.provider_version,
        outputs=[],
        metadata={"song_id": song_id, "stems": made, **sep.metadata},
        logs=[f"separated {upload.file_path} -> {', '.join(s['asset_type'] for s in made)}"],
    )
