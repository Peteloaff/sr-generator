"""Section render: execute the layering plan into stems + a mix + a master.

Called from the ``render_section`` job handler with a live session and the job
row. Creates every AudioAsset and RenderTake with full lineage, inside the job's
transaction (so a failed render leaves nothing behind). Deterministic: same
section config + same seed + same sources + same engine version -> identical
bytes.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from sr.common import dsp
from sr.common.storage import get_storage
from sr.common.synth import mock_singer_take
from sr.models.audio_asset import AudioAsset
from sr.models.enums import ROLE_STEM_TYPE
from sr.models.generation_job import GenerationJob
from sr.models.render_take import RenderTake
from sr.models.singer import Singer
from sr.models.song import SongSection
from sr.providers.base import ProviderResult
from sr.services.layering import plan_role_takes

ENGINE = "layering-engine"
ENGINE_VERSION = "layering-0.2.0"
DEFAULT_SECONDS = 8.0


def _section_seconds(section: SongSection, params: dict) -> float:
    if "duration" in params:
        return float(params["duration"])
    if section.start_time is not None and section.end_time is not None:
        span = float(section.end_time) - float(section.start_time)
        if span > 0:
            return round(span, 3)
    return DEFAULT_SECONDS


def _load_mono(path: Path, n: int) -> np.ndarray:
    stereo = dsp.load_stereo(path)
    mono = stereo.mean(axis=1)
    if mono.shape[0] >= n:
        return mono[:n]
    return np.concatenate([mono, np.zeros(n - mono.shape[0], dtype=np.float32)])


def _source_for(
    db: Session, section: SongSection, singer_id: str, n: int, seconds: float, child_seed: int
) -> tuple[np.ndarray, str, str | None]:
    take = db.scalar(
        select(AudioAsset).where(
            AudioAsset.section_id == section.id,
            AudioAsset.singer_id == singer_id,
            AudioAsset.asset_type == "source_take",
        )
    )
    if take is not None:
        canonical = get_storage().path_for(f"{Path(take.file_path).parent}/canonical.wav")
        if canonical.exists():
            return _load_mono(canonical, n), "upload", take.id
    return mock_singer_take(singer_id, section.id, seconds, child_seed)[:n], "mock", None


def _process_take(mono: np.ndarray, spec, n: int) -> np.ndarray:
    x = dsp.pan_mono(mono, spec.pan)
    x = dsp.time_offset(x, spec.timing_offset_ms)
    x = dsp.pitch_shift_cents(x, spec.pitch_cents)
    x = dsp.formant_tilt(x, spec.formant_shift)
    x = dsp.gain_db(x, spec.gain_db)
    return dsp.fit_length(x, n)


def render_section(
    db: Session, job: GenerationJob, *, section_id: str, seed: int, params: dict
) -> ProviderResult:
    section = db.get(SongSection, section_id)
    if section is None:
        raise LookupError(f"section {section_id} not found")
    song = section.song
    seconds = _section_seconds(section, params)
    n = max(1, int(round(seconds * dsp.SR)))
    storage = get_storage()
    # Keep the path short - Windows still enforces MAX_PATH for many APIs.
    base_key = f"renders/{song.id[:8]}/{job.id[:8]}"
    names = {
        s.id: s.name
        for s in db.scalars(select(Singer).where(Singer.band_id == song.band_id))
    }

    logs: list[str] = [
        f"section={section_id} seconds={seconds} seed={seed} engine={ENGINE_VERSION}"
    ]
    role_buses: dict[str, list[np.ndarray]] = {}  # grouped stem type -> role mixes
    role_summary: list[dict] = []
    all_assets: list[AudioAsset] = []

    def _asset(**kw) -> AudioAsset:
        a = AudioAsset(
            song_id=song.id, section_id=section_id, generation_job_id=job.id,
            sample_rate=dsp.SR, channels=2, duration=seconds, **kw,
        )
        db.add(a)
        db.flush()
        all_assets.append(a)
        return a

    for ri, role in enumerate(section.vocal_roles):
        specs = plan_role_takes(role, seed)
        if not specs:
            continue
        take_arrays: list[np.ndarray] = []
        take_assets: list[AudioAsset] = []
        for ti, spec in enumerate(specs):
            mono, src_kind, src_asset_id = _source_for(
                db, section, spec.singer_id, n, seconds, spec.child_seed
            )
            processed = _process_take(mono, spec, n)
            take_arrays.append(processed)
            who = names.get(spec.singer_id, spec.singer_id)
            key = f"{base_key}/r{ri}_{role.role_type}_take{ti}.wav"
            dsp.save_wav(storage.path_for(key), processed)
            ta = _asset(
                singer_id=spec.singer_id, asset_type="take_stem", file_path=key,
                label=f"{role.role_type} - {who} take {spec.take_index + 1}",
            )
            take_assets.append(ta)
            db.add(RenderTake(
                generation_job_id=job.id, vocal_role_id=role.id, singer_id=spec.singer_id,
                take_index=spec.take_index, child_seed=spec.child_seed,
                timing_offset_ms=spec.timing_offset_ms, pitch_cents=spec.pitch_cents,
                formant_shift=spec.formant_shift, gain_db=spec.gain_db, pan=spec.pan,
                source_kind=src_kind, source_asset_id=src_asset_id, output_asset_id=ta.id,
            ))

        role_mix = dsp.sum_stereo(take_arrays, n)
        role_key = f"{base_key}/r{ri}_{role.role_type}_stem.wav"
        dsp.save_wav(storage.path_for(role_key), role_mix)
        role_asset = _asset(
            asset_type="role_stem", file_path=role_key,
            label=f"{role.role_type} stem ({len(specs)} take{'s' if len(specs) != 1 else ''})",
        )
        for ta in take_assets:
            ta.parent_asset_id = role_asset.id

        grouped = ROLE_STEM_TYPE.get(role.role_type, "vocal_bus")
        role_buses.setdefault(str(grouped), []).append(role_mix)
        role_summary.append({
            "role_id": role.id, "role_type": role.role_type, "takes": len(specs),
            "singers": {names.get(s, s): sum(1 for x in specs if x.singer_id == s)
                        for s in {sp.singer_id for sp in specs}},
        })
        logs.append(f"role {role.role_type}: {len(specs)} takes -> {role_key}")

    if not role_summary:
        raise ValueError("section has no vocal roles with assignments to render")

    # grouped stem buses (isolated stems in the blueprint's taxonomy)
    bus_mixes: list[np.ndarray] = []
    for stem_type, mixes in sorted(role_buses.items()):
        bus = dsp.sum_stereo(mixes, n)
        bus_mixes.append(bus)
        key = f"{base_key}/{stem_type}.wav"
        dsp.save_wav(storage.path_for(key), bus)
        _asset(asset_type=stem_type, file_path=key, label=stem_type.replace("_", " "))

    vocal_bus, vb_norm = dsp.peak_normalize(dsp.sum_stereo(bus_mixes, n))
    vb_key = f"{base_key}/vocal_bus.wav"
    dsp.save_wav(storage.path_for(vb_key), vocal_bus)
    vb_asset = _asset(asset_type="vocal_bus", file_path=vb_key, label="all vocals")

    # optional instrumental bed
    instr = db.scalar(
        select(AudioAsset).where(
            AudioAsset.section_id == section_id, AudioAsset.asset_type == "instrumental_bed"
        )
    )
    mix_parts = [vocal_bus]
    if instr is not None:
        canonical = storage.path_for(f"{Path(instr.file_path).parent}/canonical.wav")
        if canonical.exists():
            ib = dsp.fit_length(dsp.load_stereo(canonical), n)
            mix_parts.append(ib)
            ik = f"{base_key}/stem_instrumental.wav"
            dsp.save_wav(storage.path_for(ik), ib)
            _asset(asset_type="stem_instrumental", file_path=ik, label="instrumental")

    mix, mix_norm = dsp.peak_normalize(dsp.sum_stereo(mix_parts, n))
    mix_key = f"{base_key}/mix.wav"
    dsp.save_wav(storage.path_for(mix_key), mix)
    mix_asset = _asset(asset_type="mix", file_path=mix_key, label="section mix")
    vb_asset.parent_asset_id = mix_asset.id

    master, _ = dsp.peak_normalize(dsp.gain_db(mix, 1.0), ceiling=0.95)
    master_key = f"{base_key}/master.wav"
    dsp.save_wav(storage.path_for(master_key), master)
    master_asset = _asset(asset_type="master", file_path=master_key, label="section master")
    mix_asset.parent_asset_id = master_asset.id

    db.flush()
    logs.append(
        f"mix rms={dsp.rms_dbfs(mix):.1f} dBFS  master rms={dsp.rms_dbfs(master):.1f} dBFS  "
        f"assets={len(all_assets)}"
    )
    return ProviderResult(
        provider=ENGINE,
        provider_version=ENGINE_VERSION,
        outputs=[],
        metadata={
            "section_id": section_id, "seed": seed, "seconds": seconds,
            "roles": role_summary, "master_asset_id": master_asset.id,
            "mix_asset_id": mix_asset.id,
        },
        logs=logs,
    )
