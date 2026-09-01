"""Section render: execute the layering plan into stems + a mix + a master.

Called from the ``render_section`` job handler with a live session and the job
row. Creates every AudioAsset and RenderTake with full lineage, inside the job's
transaction (so a failed render leaves nothing behind). Deterministic: same
section config + same seed + same sources + same provider versions -> identical
bytes.

Per-singer "base vocal" is resolved once (upload -> guide+voice-model conversion
-> deterministic placeholder) and cached; per-take micro-variation is layered on
top of that.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from sr.common import dsp, vocalfx
from sr.common.seeds import derive_seed
from sr.common.storage import get_storage
from sr.common.synth import mock_singer_take
from sr.models.audio_asset import AudioAsset
from sr.models.enums import ROLE_STEM_TYPE
from sr.models.generation_job import GenerationJob
from sr.models.render_take import RenderTake
from sr.models.singer import Singer
from sr.models.song import SongSection
from sr.providers.base import ProviderResult
from sr.providers.registry import get_provider
from sr.services import cache
from sr.services.consent import blocked_for_generation
from sr.services.layering import plan_role_takes
from sr.worker.progress import report as report_progress

ENGINE = "layering-engine"
ENGINE_VERSION = "layering-0.3.0"
DEFAULT_SECONDS = 8.0


def _section_seconds(section: SongSection, params: dict) -> float:
    if "duration" in params:
        return float(params["duration"])
    if section.start_time is not None and section.end_time is not None:
        span = float(section.end_time) - float(section.start_time)
        if span > 0:
            return round(span, 3)
    return DEFAULT_SECONDS


def _to_mono(x: np.ndarray, n: int, src_sr: int = dsp.SR) -> np.ndarray:
    if x.ndim == 2:
        x = x.mean(axis=1)
    if src_sr != dsp.SR and x.size:
        x = dsp.fit_length(
            dsp.resample(x.reshape(-1, 1), int(round(len(x) * dsp.SR / src_sr))), n
        )[:, 0]
    if x.shape[0] >= n:
        return x[:n].astype(np.float32)
    return np.concatenate([x, np.zeros(n - x.shape[0], dtype=np.float32)]).astype(np.float32)


def _base_vocal(
    db: Session, section: SongSection, singer: Singer, n: int, seconds: float, seed: int
) -> tuple[np.ndarray, str, str | None]:
    """Resolve one singer's dry vocal for this section (before per-take variation)."""
    storage = get_storage()

    take = db.scalar(
        select(AudioAsset).where(
            AudioAsset.section_id == section.id,
            AudioAsset.singer_id == singer.id,
            AudioAsset.asset_type == "source_take",
        )
    )
    if take is not None:
        canonical_key = f"{Path(take.file_path).parent}/canonical.wav"
        if storage.exists(canonical_key):
            return _to_mono(storage.read_stereo(canonical_key), n), "upload", take.id

    guide = db.scalar(
        select(AudioAsset).where(
            AudioAsset.section_id == section.id, AudioAsset.asset_type == "guide_vocal"
        )
    )
    if (
        guide is not None
        and singer.training_status == "ready"
        and singer.voice_profile_json
    ):
        guide_key = f"{Path(guide.file_path).parent}/canonical.wav"
        if storage.exists(guide_key):
            guide_canonical = storage.ensure_local(guide_key)
            provider = get_provider("voice")
            ck = cache.key_for(
                "voice_conversion",
                provider.version,
                cache.hash_file(guide_canonical),
                singer.voice_profile_json,
            )
            hit = cache.lookup(ck, db=db)
            if hit is not None:
                return _to_mono(storage.read_stereo(hit), n), "converted", guide.id
            conv = provider.convert(
                guide_path=guide_canonical,
                profile=singer.voice_profile_json,
                params={},
                seed=derive_seed(seed, "conversion", singer.id),
            )
            fk = cache.store(
                ck, kind="voice_conversion", provider=conv.provider,
                provider_version=conv.provider_version,
                samples=conv.samples, sample_rate=conv.sample_rate, db=db,
            )
            return _to_mono(storage.read_stereo(fk), n), "converted", guide.id

    placeholder_seed = derive_seed(seed, "placeholder", singer.id)
    placeholder = mock_singer_take(singer.id, section.id, seconds, placeholder_seed)
    return placeholder[:n], "mock", None


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
    base_key = f"renders/{song.id[:8]}/{job.id[:8]}"
    mode = str(params.get("mode", "ensemble"))
    is_flat = mode == "flat"
    # Stage 9: reroll only the named roles (perturb their plan seed); every other
    # role re-derives byte-identically because its inputs and seed are unchanged.
    role_salts: dict[str, int] = {
        str(k): int(v) for k, v in (params.get("role_seed_salt") or {}).items()
    }

    assigned_ids = {a.singer_id for r in section.vocal_roles for a in r.assignments}
    singers = {
        s.id: s for s in db.scalars(select(Singer).where(Singer.id.in_(assigned_ids or {""})))
    }
    blocked = blocked_for_generation(singers.values())
    if blocked:
        raise PermissionError(f"consent_generation missing for: {', '.join(blocked)}")
    names = {sid: s.name for sid, s in singers.items()}

    report_progress(db, job, 0.05, f"render start ({seconds}s, {len(section.vocal_roles)} roles)")
    logs: list[str] = [
        f"section={section_id} seconds={seconds} seed={seed} engine={ENGINE_VERSION}"
    ]
    role_buses: dict[str, list[np.ndarray]] = {}
    role_summary: list[dict] = []
    all_assets: list[AudioAsset] = []
    base_cache: dict[str, tuple[np.ndarray, str, str | None]] = {}

    def _asset(**kw) -> AudioAsset:
        a = AudioAsset(
            song_id=song.id, section_id=section_id, generation_job_id=job.id,
            sample_rate=dsp.SR, channels=2, duration=seconds, **kw,
        )
        db.add(a)
        db.flush()
        all_assets.append(a)
        return a

    def _base_for(singer_id: str) -> tuple[np.ndarray, str, str | None]:
        if singer_id not in base_cache:
            base_cache[singer_id] = _base_vocal(
                db, section, singers[singer_id], n, seconds, seed
            )
        return base_cache[singer_id]

    roles = list(enumerate(section.vocal_roles))
    for ri, role in roles:
        role_seed = (
            derive_seed(seed, "reroll", role_salts[role.id])
            if role.id in role_salts
            else seed
        )
        specs = plan_role_takes(role, role_seed, flat=is_flat)
        if not specs:
            continue
        take_arrays: list[np.ndarray] = []
        take_assets: list[AudioAsset] = []
        for ti, spec in enumerate(specs):
            base, src_kind, src_asset_id = _base_for(spec.singer_id)
            processed = _process_take(base, spec, n)
            take_arrays.append(processed)
            who = names.get(spec.singer_id, spec.singer_id)
            key = f"{base_key}/r{ri}_{role.role_type}_take{ti}.wav"
            storage.save_wav(key, processed)
            ta = _asset(
                singer_id=spec.singer_id, asset_type="take_stem", file_path=key,
                label=f"{role.role_type} - {who} take {spec.take_index + 1} ({src_kind})",
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
        fx_log: list[str] = []
        if not is_flat:
            role_mix = (role_mix * vocalfx.stack_gain(len(specs))).astype(np.float32)
            role_mix, fx_log = vocalfx.apply_chain(role_mix, role.processing_json)
        role_key = f"{base_key}/r{ri}_{role.role_type}_stem.wav"
        storage.save_wav(role_key, role_mix)
        chain_note = f" [{'+'.join(fx_log)}]" if fx_log else ""
        role_asset = _asset(
            asset_type="role_stem", file_path=role_key,
            label=f"{role.role_type} stem "
            f"({len(specs)} take{'s' if len(specs) != 1 else ''}){chain_note}",
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
        if roles:
            frac = 0.1 + 0.7 * (ri + 1) / len(roles)
            report_progress(db, job, frac, f"rendered {role.role_type}")

    if not role_summary:
        raise ValueError("section has no vocal roles with assignments to render")

    src_kinds = sorted({k for _, k, _ in base_cache.values()})
    logs.append(f"source kinds: {', '.join(src_kinds)}")
    report_progress(db, job, 0.85, "mixing stems")

    bus_mixes: list[np.ndarray] = []
    for stem_type, mixes in sorted(role_buses.items()):
        bus = dsp.sum_stereo(mixes, n)
        bus_mixes.append(bus)
        key = f"{base_key}/{stem_type}.wav"
        storage.save_wav(key, bus)
        _asset(asset_type=stem_type, file_path=key, label=stem_type.replace("_", " "))

    vocal_bus, _ = dsp.peak_normalize(dsp.sum_stereo(bus_mixes, n))
    vb_key = f"{base_key}/vocal_bus.wav"
    storage.save_wav(vb_key, vocal_bus)
    vb_asset = _asset(asset_type="vocal_bus", file_path=vb_key, label=f"all vocals ({mode})")

    ab = {
        "mode": mode,
        "width_ratio": round(vocalfx.width_ratio(vocal_bus), 4),
        "stereo_correlation": round(vocalfx.stereo_correlation(vocal_bus), 4),
        "mono_compat": round(vocalfx.mono_compat(vocal_bus), 4),
        "vocal_rms_dbfs": round(dsp.rms_dbfs(vocal_bus), 2),
    }
    logs.append(
        f"A/B [{mode}] width={ab['width_ratio']} corr={ab['stereo_correlation']} "
        f"mono_compat={ab['mono_compat']}"
    )

    instr = db.scalar(
        select(AudioAsset).where(
            AudioAsset.section_id == section_id, AudioAsset.asset_type == "instrumental_bed"
        )
    )
    mix_parts = [vocal_bus]
    if instr is not None:
        instr_key = f"{Path(instr.file_path).parent}/canonical.wav"
        if storage.exists(instr_key):
            ib = dsp.fit_length(storage.read_stereo(instr_key), n)
            mix_parts.append(ib)
            ik = f"{base_key}/stem_instrumental.wav"
            storage.save_wav(ik, ib)
            _asset(asset_type="stem_instrumental", file_path=ik, label="instrumental")

    mix, _ = dsp.peak_normalize(dsp.sum_stereo(mix_parts, n))
    mix_key = f"{base_key}/mix.wav"
    storage.save_wav(mix_key, mix)
    mix_asset = _asset(asset_type="mix", file_path=mix_key, label="section mix")
    vb_asset.parent_asset_id = mix_asset.id

    report_progress(db, job, 0.95, "mastering")
    master, _ = dsp.peak_normalize(dsp.gain_db(mix, 1.0), ceiling=0.95)
    master_key = f"{base_key}/master.wav"
    storage.save_wav(master_key, master)
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
            "section_id": section_id, "seed": seed, "seconds": seconds, "mode": mode,
            "roles": role_summary, "source_kinds": src_kinds, "ab": ab,
            "master_asset_id": master_asset.id, "mix_asset_id": mix_asset.id,
        },
        logs=logs,
    )
