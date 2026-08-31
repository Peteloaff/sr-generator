"""Assemble a full-song mix: the original recording with selected sections'
vocals replaced by band renders, everything else untouched.

Untouched time ranges are copied verbatim from the original mix, so "export a new
mix without touching unrelated sections" is literally true (byte-identical
outside the replaced windows, modulo the short edge crossfades).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from sr.common import dsp
from sr.common.storage import get_storage
from sr.models.audio_asset import AudioAsset
from sr.models.generation_job import GenerationJob
from sr.models.song import Song
from sr.providers.base import ProviderResult
from sr.worker.progress import report as report_progress

_XFADE = 0.012  # seconds


def _canonical(asset: AudioAsset) -> Path:
    return get_storage().path_for(f"{Path(asset.file_path).parent}/canonical.wav")


def _latest(
    db: Session, song_id: str, asset_type: str, section_id: str | None
) -> AudioAsset | None:
    stmt = select(AudioAsset).where(
        AudioAsset.song_id == song_id, AudioAsset.asset_type == asset_type
    )
    stmt = stmt.where(
        AudioAsset.section_id == section_id if section_id
        else AudioAsset.section_id.is_(None)
    )
    return db.scalar(stmt.order_by(AudioAsset.version.desc(), AudioAsset.created_at.desc()))


def _latest_render_vocal(db: Session, song_id: str, section_id: str) -> np.ndarray | None:
    job = db.scalar(
        select(GenerationJob)
        .where(
            GenerationJob.song_id == song_id,
            GenerationJob.section_id == section_id,
            GenerationJob.job_type == "render_section",
            GenerationJob.status == "succeeded",
        )
        .order_by(GenerationJob.completed_at.desc())
    )
    if job is None:
        return None
    vb = db.scalar(
        select(AudioAsset).where(
            AudioAsset.generation_job_id == job.id, AudioAsset.asset_type == "vocal_bus"
        )
    )
    if vb is None:
        return None
    return dsp.load_stereo(get_storage().path_for(vb.file_path))


def assemble_song(
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
        raise ValueError("song has no uploaded mix to assemble against")

    original = dsp.load_stereo(_canonical(upload))
    total = original.shape[0]
    sr = dsp.SR
    out = original.copy()

    instr_asset = _latest(db, song_id, "stem_instrumental", None)
    instrumental = (
        dsp.fit_length(
            dsp.load_stereo(get_storage().path_for(instr_asset.file_path)), total
        )
        if instr_asset is not None
        else None
    )

    xf = int(_XFADE * sr)
    replaced: list[dict] = []
    sections = sorted(
        (s for s in song.sections if s.start_time is not None and s.end_time is not None),
        key=lambda s: s.start_time,
    )
    for idx, section in enumerate(sections):
        vocals = _latest_render_vocal(db, song_id, section.id)
        if vocals is None:
            continue
        s = max(0, int(section.start_time * sr))
        e = min(total, int(section.end_time * sr))
        if e - s < 2 * xf:
            continue
        bed = instrumental[s:e] if instrumental is not None else original[s:e] * 0.0
        voc = dsp.fit_length(vocals, e - s)
        new, _ = dsp.peak_normalize(bed + voc, ceiling=0.99)

        seg = out[s:e].copy()
        ramp = np.linspace(0.0, 1.0, xf, dtype=np.float32)[:, None]
        new[:xf] = seg[:xf] * (1 - ramp) + new[:xf] * ramp
        new[-xf:] = seg[-xf:] * ramp[::-1] + new[-xf:] * (1 - ramp[::-1])
        out[s:e] = new
        replaced.append(
            {"section_id": section.id, "start": section.start_time, "end": section.end_time}
        )
        frac = 0.2 + 0.7 * (idx + 1) / max(1, len(sections))
        report_progress(db, job, frac, "spliced section")

    if not replaced:
        raise ValueError("no rendered sections to assemble - render a section first")

    storage = get_storage()
    prior = db.scalar(
        select(AudioAsset)
        .where(AudioAsset.song_id == song_id, AudioAsset.asset_type == "song_mix")
        .order_by(AudioAsset.version.desc())
    )
    version = (prior.version + 1) if prior else 1
    key = f"mixes/{song_id[:8]}/song_mix_v{version}.wav"
    dsp.save_wav(storage.path_for(key), out, sr)
    asset = AudioAsset(
        song_id=song_id, generation_job_id=job.id, parent_asset_id=upload.id,
        asset_type="song_mix", file_path=key, version=version,
        sample_rate=sr, channels=2, duration=round(total / sr, 3),
        label=f"full-song mix v{version} ({len(replaced)} section"
        f"{'s' if len(replaced) != 1 else ''} replaced)",
    )
    db.add(asset)
    db.flush()
    return ProviderResult(
        provider="assembly-engine",
        provider_version="assembly-0.5.0",
        outputs=[],
        metadata={"song_mix_asset_id": asset.id, "version": version, "replaced": replaced},
        logs=[f"assembled song_mix v{version}: {len(replaced)} section(s) replaced"],
    )
