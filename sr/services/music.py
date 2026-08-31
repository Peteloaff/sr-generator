"""Band-specific music generation (Stage 7).

train_band_adapter distils the Band DNA into a conditioning descriptor;
generate_instrumental renders a section instrumental with the music provider and
wires it in as the section's instrumental bed, so band vocals render over it.
"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from sr.common import dsp
from sr.common.storage import get_storage
from sr.models.audio_asset import AudioAsset
from sr.models.band import Band
from sr.models.band_adapter import BandAdapter
from sr.models.generation_job import GenerationJob
from sr.models.song import SongSection
from sr.providers.base import ProviderResult
from sr.providers.registry import get_provider
from sr.services.dna import band_dna
from sr.services.manifest import build_manifest
from sr.worker.progress import report as report_progress


def train_band_adapter(
    db: Session, job: GenerationJob, *, band_id: str, params: dict
) -> ProviderResult:
    band = db.get(Band, band_id)
    if band is None:
        raise LookupError(f"band {band_id} not found")
    provider = get_provider("music")
    if not getattr(provider, "trains_adapter", False):
        raise ValueError(f"music provider {provider.name!r} does not train adapters")

    report_progress(db, job, 0.2, "building dataset manifest")
    manifest = build_manifest(db, band, strict=True)
    if manifest["totals"]["count"] == 0:
        raise ValueError("no approved reference songs to train an adapter from")
    dna = band_dna(db, band)

    report_progress(db, job, 0.5, "distilling band character")
    spec = provider.train_adapter(manifest=manifest, dna=dna, params=params)

    name = params.get("name") or f"{band.slug}-{spec.dataset_version[:8] or 'adapter'}"
    existing = db.scalar(
        select(BandAdapter).where(BandAdapter.band_id == band_id, BandAdapter.name == name)
    )
    if existing is not None:
        existing.spec_json = spec.spec
        existing.provider = spec.provider
        existing.provider_version = spec.provider_version
        existing.dataset_version = spec.dataset_version
        adapter = existing
    else:
        adapter = BandAdapter(
            band_id=band_id, name=name, provider=spec.provider,
            provider_version=spec.provider_version, dataset_version=spec.dataset_version,
            spec_json=spec.spec,
        )
        db.add(adapter)
    db.flush()
    return ProviderResult(
        provider=spec.provider, provider_version=spec.provider_version, outputs=[],
        metadata={"adapter_id": adapter.id, "dataset_version": spec.dataset_version,
                  "spec": spec.spec},
        logs=[f"trained adapter {name!r} from {manifest['totals']['count']} references"],
    )


def _section_key_bpm(section: SongSection, adapter_spec: dict) -> tuple[float | None, str | None]:
    song = section.song
    bpm = song.bpm or adapter_spec.get("tempo_prior")
    key = song.key or adapter_spec.get("key_prior")
    return bpm, key


def generate_instrumental(
    db: Session, job: GenerationJob, *, section_id: str, seed: int, params: dict
) -> ProviderResult:
    section = db.get(SongSection, section_id)
    if section is None:
        raise LookupError(f"section {section_id} not found")
    song = section.song

    adapter_spec: dict = {}
    adapter_id = params.get("adapter_id")
    if adapter_id:
        adapter = db.get(BandAdapter, adapter_id)
        if adapter is None or adapter.band_id != song.band_id:
            raise ValueError("adapter not found for this band")
        adapter_spec = adapter.spec_json or {}

    seconds = params.get("duration")
    if seconds is None and section.start_time is not None and section.end_time is not None:
        seconds = round(section.end_time - section.start_time, 3)
    seconds = float(seconds or 8.0)

    bpm, key = _section_key_bpm(section, adapter_spec)
    gen_params = {
        "duration": seconds,
        **({"bpm": params["bpm"]} if params.get("bpm") else ({"bpm": bpm} if bpm else {})),
        **({"key": params["key"]} if params.get("key") else ({"key": key} if key else {})),
    }

    report_progress(db, job, 0.3, "generating instrumental")
    provider = get_provider("music")
    result = provider.generate(
        prompt=str(params.get("prompt", "band instrumental")),
        params=gen_params, seed=seed, adapter=adapter_spec or None,
    )

    storage = get_storage()
    base = f"references/{song.band_id}/{song.id}/{section_id}/instrumental"
    key_path = f"{base}/canonical.wav"
    dsp.save_wav(storage.path_for(key_path), result.audio, result.sample_rate)

    for old in db.scalars(
        select(AudioAsset).where(
            AudioAsset.section_id == section_id, AudioAsset.asset_type == "instrumental_bed"
        )
    ):
        db.delete(old)
    db.flush()

    m = result.metadata
    label = f"generated: {m.get('key', '?')} @ {m.get('bpm', '?')} bpm"
    if m.get("progression"):
        label += f" ({m['progression']})"
    asset = AudioAsset(
        song_id=song.id, section_id=section_id, generation_job_id=job.id,
        asset_type="instrumental_bed", file_path=key_path, label=label,
        sample_rate=result.sample_rate, channels=2,
        duration=round(result.audio.shape[0] / result.sample_rate, 3),
    )
    db.add(asset)
    db.flush()
    return ProviderResult(
        provider=result.provider, provider_version=result.provider_version, outputs=[],
        metadata={
            "section_id": section_id, "asset_id": asset.id, "seed": seed,
            "adapter_id": adapter_id, **result.metadata,
        },
        logs=[f"generated {seconds}s instrumental -> {Path(key_path).name}"],
    )
