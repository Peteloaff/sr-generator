"""Stage 11 - experimental vocal morph / timbre blend.

Renders a *preview* of an automated transition from one singer identity to another
across a section, with quality flags. Preview-only: a morph is never wired into a
section mix by this stage, and a low-quality morph is blocked from being
committed. The whole feature is gated behind ``SR_EXPERIMENTAL_MORPH``.
"""

from __future__ import annotations

import numpy as np
from sqlalchemy.orm import Session

from sr.common import dsp
from sr.common.seeds import derive_seed
from sr.common.storage import get_storage
from sr.models.audio_asset import AudioAsset
from sr.models.generation_job import GenerationJob
from sr.models.singer import Singer
from sr.models.song import SongSection
from sr.models.vocal_morph import VocalMorph
from sr.providers.base import ProviderResult
from sr.services.consent import blocked_for_generation
from sr.services.render import _base_vocal, _section_seconds
from sr.worker.progress import report as report_progress

MORPH_VERSION = "morph-rnd-0.11.0"
_MIN_USABLE_SCORE = 0.6


def _weights(n: int, curve: str, start: float, end: float) -> np.ndarray:
    s = int(np.clip(start, 0.0, 1.0) * n)
    e = int(np.clip(end, 0.0, 1.0) * n)
    if e <= s:
        e = min(n, s + 1)
    x = np.linspace(0.0, 1.0, e - s, dtype=np.float64)
    ramp = x * x * (3 - 2 * x) if curve == "scurve" else x
    w = np.zeros(n, dtype=np.float64)
    w[s:e] = ramp
    w[e:] = 1.0
    return w


def _envelope(x: np.ndarray, sr: int = dsp.SR) -> np.ndarray:
    win = max(1, sr // 33)  # ~30 ms
    power = np.convolve(x.astype(np.float64) ** 2, np.ones(win) / win, mode="same")
    return np.sqrt(power)[::win]


def _quality(
    mixed: np.ndarray, a: np.ndarray, b: np.ndarray, w: np.ndarray,
    raw_peak: float, sr: int = dsp.SR,
) -> dict:
    flags: list[str] = []
    if raw_peak > 1.25:
        flags.append("clipping")  # gross level problem even before safety gain

    region = (w > 0.02) & (w < 0.98)
    if region.sum() > sr // 10:
        ea, eb = _envelope(a[region]), _envelope(b[region])
        m = min(len(ea), len(eb))
        if m > 4 and ea[:m].std() > 1e-7 and eb[:m].std() > 1e-7:
            env_corr = float(np.corrcoef(ea[:m], eb[:m])[0, 1])
        else:
            env_corr = 0.0
        if env_corr < 0.3:
            # the two performances don't track each other - the blend will pump
            flags.append("poor_alignment")

        # energy continuity across the morph region
        idx = np.where(region)[0]
        mid = mixed[region]
        for edge in (mixed[: idx[0]], mixed[idx[-1] + 1 :]):
            if edge.size > sr // 20 and mid.size:
                jump = abs(
                    dsp.rms_dbfs(edge.reshape(-1, 1)) - dsp.rms_dbfs(mid.reshape(-1, 1))
                )
                if jump > 12.0:
                    flags.append("energy_jump")
                    break

    score = round(max(0.0, 1.0 - 0.3 * len(set(flags))), 3)
    usable = score >= _MIN_USABLE_SCORE and "poor_alignment" not in flags
    return {
        "score": score,
        "flags": sorted(set(flags)),
        "usable": bool(usable),
        "raw_peak": round(raw_peak, 4),
        "env_corr": round(env_corr, 3) if region.sum() > sr // 10 else None,
        "min_usable_score": _MIN_USABLE_SCORE,
    }


def render_morph_preview(
    db: Session, job: GenerationJob, *, morph_id: str, seed: int, params: dict
) -> ProviderResult:
    morph = db.get(VocalMorph, morph_id)
    if morph is None:
        raise LookupError(f"morph {morph_id} not found")
    section = db.get(SongSection, morph.section_id)
    if section is None:
        raise LookupError("morph section not found")
    a_singer = db.get(Singer, morph.from_singer_id)
    b_singer = db.get(Singer, morph.to_singer_id)
    if a_singer is None or b_singer is None:
        raise LookupError("morph singer not found")
    blocked = blocked_for_generation([a_singer, b_singer])
    if blocked:
        raise PermissionError(f"consent_generation missing for: {', '.join(blocked)}")

    seconds = _section_seconds(section, {})
    n = max(1, int(round(seconds * dsp.SR)))
    report_progress(db, job, 0.2, "resolving both singer vocals")
    a_vocal, a_kind, _ = _base_vocal(db, section, a_singer, n, seconds, derive_seed(seed, "morphA"))
    b_vocal, b_kind, _ = _base_vocal(db, section, b_singer, n, seconds, derive_seed(seed, "morphB"))
    a_vocal = dsp.fit_length(a_vocal.reshape(-1, 1), n)[:, 0]
    b_vocal = dsp.fit_length(b_vocal.reshape(-1, 1), n)[:, 0]

    w = _weights(n, morph.curve, morph.start_frac, morph.end_frac)
    if morph.curve == "equal_power":
        ga, gb = np.cos(w * np.pi / 2), np.sin(w * np.pi / 2)
    else:
        ga, gb = 1.0 - w, w
    mixed = (a_vocal * ga + b_vocal * gb).astype(np.float32)
    raw_peak = float(np.max(np.abs(mixed))) if mixed.size else 0.0
    if raw_peak > 0.95:
        mixed = (mixed * (0.95 / raw_peak)).astype(np.float32)  # safety gain

    report_progress(db, job, 0.7, "scoring morph quality")
    quality = _quality(mixed, a_vocal, b_vocal, w, raw_peak)

    storage = get_storage()
    key = f"morphs/{section.id[:8]}/{morph_id[:8]}_preview.wav"
    stereo = np.stack([mixed, mixed], axis=1).astype(np.float32)
    dsp.save_wav(storage.path_for(key), stereo, dsp.SR)

    if morph.preview_asset_id:
        old = db.get(AudioAsset, morph.preview_asset_id)
        if old is not None:
            db.delete(old)
        db.flush()
    asset = AudioAsset(
        song_id=section.song_id, section_id=section.id, generation_job_id=job.id,
        asset_type="morph_preview", file_path=key,
        label=f"morph {a_singer.name} -> {b_singer.name} ({morph.curve})",
        sample_rate=dsp.SR, channels=2, duration=round(n / dsp.SR, 3),
    )
    db.add(asset)
    db.flush()
    morph.preview_asset_id = asset.id
    morph.quality_json = quality
    if not quality["usable"]:
        morph.committed = False
    db.flush()

    return ProviderResult(
        provider="morph-rnd", provider_version=MORPH_VERSION, outputs=[],
        metadata={
            "morph_id": morph_id, "section_id": section.id, "seed": seed,
            "from": a_singer.name, "to": b_singer.name,
            "from_source": a_kind, "to_source": b_kind,
            "curve": morph.curve, "quality": quality, "preview_asset_id": asset.id,
        },
        logs=[
            f"morph {a_singer.name}->{b_singer.name} {morph.curve} "
            f"[{morph.start_frac:.2f}-{morph.end_frac:.2f}]",
            f"quality score {quality['score']} flags={quality['flags']} "
            f"usable={quality['usable']}",
        ],
    )
