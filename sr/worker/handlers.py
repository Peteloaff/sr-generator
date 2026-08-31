"""Job-type -> handler routing.

A handler takes ``(GenerationJob, Session)`` - the job is already marked running
inside the session - and returns a ProviderResult. Simple providers put file
specs in ``result.outputs`` and the runner creates the AudioAssets; handlers that
build their own asset graph (``render_section``) create the rows themselves and
return empty outputs.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from sr.common.storage import get_storage
from sr.config import get_settings
from sr.models.audio_asset import AudioAsset
from sr.models.generation_job import GenerationJob
from sr.models.singer import Singer
from sr.providers import base
from sr.providers.registry import get_provider
from sr.services.consent import require_training
from sr.services.render import render_section

Handler = Callable[[GenerationJob, Session], base.ProviderResult]


def _seed(job: GenerationJob) -> int:
    return job.seed if job.seed is not None else get_settings().default_seed


def _mock_generation(job: GenerationJob, db: Session) -> base.ProviderResult:
    params = job.parameters_json or {}
    provider = get_provider("music")
    job.append_log(f"provider={provider.name}@{provider.version} seed={_seed(job)}")
    return provider.generate(
        prompt=str(params.get("prompt", "untitled")), params=params, seed=_seed(job)
    )


def _analyze_reference(job: GenerationJob, db: Session) -> base.ProviderResult:
    params = job.parameters_json or {}
    return get_provider("analysis").analyze(source_asset=str(params.get("source_asset", "")))


def _separate_stems(job: GenerationJob, db: Session) -> base.ProviderResult:
    params = job.parameters_json or {}
    return get_provider("stem").separate(
        source_asset=str(params.get("source_asset", "")), params=params
    )


def _train_singer(job: GenerationJob, db: Session) -> base.ProviderResult:
    params = job.parameters_json or {}
    singer = db.get(Singer, str(params.get("singer_id", "")))
    if singer is None:
        raise LookupError("train_singer job requires a valid singer_id")
    require_training(singer)  # ConsentError -> job fails safely

    storage = get_storage()
    samples = db.scalars(
        select(AudioAsset).where(
            AudioAsset.singer_id == singer.id, AudioAsset.asset_type == "singer_sample"
        )
    )
    paths: list[Path] = []
    for a in samples:
        canonical = storage.path_for(f"{Path(a.file_path).parent}/canonical.wav")
        if canonical.exists():
            paths.append(canonical)
    if not paths:
        raise ValueError("no training samples uploaded for this singer")

    provider = get_provider("voice")
    singer.training_status = "training"
    db.flush()
    profile = provider.analyze(paths, singer_ref=singer.name)

    singer.voice_profile_json = profile
    singer.voice_model_provider = provider.name
    singer.voice_model_path_or_id = getattr(provider, "version", None)
    singer.training_samples = len(paths)
    singer.training_status = "ready"

    return base.ProviderResult(
        provider=provider.name,
        provider_version=getattr(provider, "version", "0"),
        outputs=[],
        metadata={"singer_id": singer.id, "profile": profile, "samples": len(paths)},
        logs=[f"trained {singer.name!r} voice model from {len(paths)} sample(s): {profile}"],
    )


def _master(job: GenerationJob, db: Session) -> base.ProviderResult:
    params = job.parameters_json or {}
    return get_provider("mastering").master(
        mix_asset=str(params.get("mix_asset", "")), params=params
    )


def _render_section(job: GenerationJob, db: Session) -> base.ProviderResult:
    params = job.parameters_json or {}
    if not job.section_id:
        raise ValueError("render_section job requires section_id")
    return render_section(
        db, job, section_id=job.section_id, seed=_seed(job), params=params
    )


_HANDLERS: dict[str, Handler] = {
    "mock_generation": _mock_generation,
    "analyze_reference": _analyze_reference,
    "separate_stems": _separate_stems,
    "train_singer": _train_singer,
    "render_section": _render_section,
    "master": _master,
}


def get_handler(job_type: str) -> Handler:
    try:
        return _HANDLERS[job_type]
    except KeyError as exc:
        raise KeyError(f"no handler for job_type {job_type!r}") from exc


def known_job_types() -> list[str]:
    return sorted(_HANDLERS)
