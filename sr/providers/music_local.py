"""LocalSynthMusicProvider - a deterministic instrumental arranger + synth.

Not a music model. It renders drums / bass / chords / arp in the requested key
and tempo, shaped by a band 'character' vector. ``train_adapter`` distils the
Band DNA (Stage 6) into that vector. A real model (ACE-Step / MusicGen / a LoRA)
implements the same ``generate`` / ``train_adapter`` contract.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from sr.common import musicgen
from sr.common.dsp import SR
from sr.providers.base import BandAdapterSpec, MusicGeneration, MusicGenerationProvider


class LocalSynthMusicProvider(MusicGenerationProvider):
    name = "local_synth"
    version = "local-synth-music-0.7.0"
    trains_adapter = True

    def train_adapter(
        self, *, manifest: dict[str, Any], dna: dict[str, Any], params: dict[str, Any]
    ) -> BandAdapterSpec:
        emb = dna.get("mean_embedding") or [0.0] * 34
        centroid = float(emb[-2]) if len(emb) >= 2 else 0.2
        zcr = float(emb[-1]) if len(emb) >= 1 else 0.1
        bpm = (dna.get("bpm") or {}).get("median") or 120.0
        keys = dna.get("key_distribution") or {}
        top_key = next(iter(keys), "C major")

        spec = {
            "character": {
                "brightness": round(float(np.clip((centroid - 0.15) * 4.0, -1.0, 1.0)), 3),
                "drum_busy": round(float(np.clip(zcr * 7.0, 0.1, 1.0)), 3),
                "drive": round(float(np.clip(0.15 + centroid * 0.6, 0.0, 0.6)), 3),
            },
            "tempo_prior": round(float(bpm), 1),
            "key_prior": top_key,
            "energy_profile": dna.get("energy_profile"),
            "trained_from": {
                "references": manifest.get("totals", {}).get("count", 0),
                "total_seconds": manifest.get("totals", {}).get("total_seconds", 0),
            },
        }
        return BandAdapterSpec(
            spec=spec,
            provider=self.name,
            provider_version=self.version,
            dataset_version=manifest.get("dataset_version", ""),
        )

    def generate(
        self, *, prompt: str, params: dict[str, Any], seed: int, adapter: dict[str, Any] | None
    ) -> MusicGeneration:
        adapter = adapter or {}
        bpm = params.get("bpm") or adapter.get("tempo_prior") or 120.0
        key = params.get("key") or adapter.get("key_prior") or "C major"
        seconds = float(params.get("duration", 8.0))
        character = dict(adapter.get("character") or {})
        for k in ("brightness", "drive", "drum_busy"):
            if k in params:
                character[k] = float(params[k])
        energy = params.get("energy_curve") or adapter.get("energy_profile")

        out = musicgen.generate(
            bpm=float(bpm), key=str(key), seconds=seconds, seed=seed,
            character=character, energy_curve=energy, sr=SR,
        )
        meta = out["metadata"]
        meta["prompt"] = prompt
        meta["adapter_applied"] = bool(adapter)
        return MusicGeneration(
            audio=out["audio"], sample_rate=out["sample_rate"],
            provider=self.name, provider_version=self.version, metadata=meta,
        )
