"""Player style-model training (Stage 13).

Separate each uploaded song into per-instrument stems, keep the player's
instrument, and learn a compact style profile (drive/tone/attack/density/
dynamics/swing) from it. The profile is a set of *tendencies*, not a recording -
Stage 14 applies it to brand-new parts.
"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from sr.common.storage import get_storage
from sr.models.audio_asset import AudioAsset
from sr.models.generation_job import GenerationJob
from sr.models.player import ROLE_STEM, Player
from sr.providers.base import ProviderResult
from sr.providers.registry import get_provider
from sr.services.consent import require_player_training
from sr.worker.progress import report as report_progress

_STEM_ASSET = {  # separated stem key -> the asset_type we store it under
    "drums": "stem_drums",
    "bass": "stem_bass",
    "guitar": "stem_guitar",
    "keys": "stem_keys",
}


def _canonical(asset: AudioAsset) -> str:
    return f"{Path(asset.file_path).parent}/canonical.wav"


def train_player(
    db: Session, job: GenerationJob, *, player_id: str, params: dict
) -> ProviderResult:
    player = db.get(Player, player_id)
    if player is None:
        raise LookupError(f"player {player_id} not found")
    require_player_training(player)  # ConsentError -> job fails safely

    storage = get_storage()
    samples = list(
        db.scalars(
            select(AudioAsset)
            .where(
                AudioAsset.player_id == player.id,
                AudioAsset.asset_type == "player_sample",
            )
            .order_by(AudioAsset.created_at, AudioAsset.id)
        )
    )
    sample_paths = [
        storage.ensure_local(_canonical(a)) for a in samples if storage.exists(_canonical(a))
    ]
    if not sample_paths:
        raise ValueError("no training samples uploaded for this player")

    want = ROLE_STEM[player.role]          # "guitar" | "bass" | "drums" | "keys"
    stem_asset_type = _STEM_ASSET[want]
    player.training_status = "training"
    db.flush()

    separator = get_provider("multistem")
    stylist = get_provider("playerstyle")

    # drop any stems from a previous training run
    for old in db.scalars(
        select(AudioAsset).where(
            AudioAsset.player_id == player.id, AudioAsset.asset_type == "player_stem"
        )
    ):
        db.delete(old)
    db.flush()

    stem_paths: list[Path] = []
    for i, (asset, src) in enumerate(zip(samples, sample_paths, strict=False)):
        report_progress(db, job, 0.1 + 0.7 * i / max(1, len(sample_paths)),
                        f"separating sample {i + 1}/{len(sample_paths)}")
        sep = separator.separate(source_path=src, params={})
        arr = sep.stems.get(stem_asset_type)
        if arr is None:
            raise ValueError(
                f"separation provider {sep.provider!r} did not return {stem_asset_type!r}"
            )
        key = f"models/players/{player.band_id}/{player.id}/stem_{i:03d}_{want}.wav"
        storage.save_wav(key, arr, sep.sample_rate)
        db.add(AudioAsset(
            player_id=player.id, parent_asset_id=asset.id, generation_job_id=job.id,
            asset_type="player_stem", file_path=key,
            label=f"{player.name} - {want} (sample {i + 1})",
            sample_rate=sep.sample_rate, channels=2,
            duration=round(arr.shape[0] / sep.sample_rate, 3),
        ))
        stem_paths.append(storage.ensure_local(key))
    db.flush()

    report_progress(db, job, 0.85, "learning style")
    profile = stylist.analyze(stem_paths, role=player.role, bpm=float(params.get("bpm") or 0.0))

    player.style_profile_json = profile
    player.style_model_provider = stylist.name
    player.style_model_path_or_id = getattr(separator, "version", None)
    player.training_samples = len(stem_paths)
    player.training_status = "ready"
    db.flush()

    return ProviderResult(
        provider=stylist.name,
        provider_version=getattr(stylist, "version", "0"),
        outputs=[],
        metadata={
            "player_id": player.id, "role": player.role, "profile": profile,
            "samples": len(stem_paths), "separation_provider": sep.provider,
        },
        logs=[
            f"separated {len(stem_paths)} sample(s) with {sep.provider}",
            f"learned {player.role} style for {player.name!r}: {profile}",
        ],
    )
