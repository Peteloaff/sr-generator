"""HttpMusicProvider - an ACE-Step / MusicGen-class model behind an HTTP service.

``POST /generate`` (JSON: prompt, bpm, key, duration, seed, adapter) -> WAV body.
``POST /train-adapter`` (JSON: manifest, dna, params) -> JSON adapter spec.
Set ``SR_MUSIC_PROVIDER=http`` + ``SR_MUSIC_HTTP_URL``.
"""

from __future__ import annotations

import io
from typing import Any

import numpy as np

from sr.common.dsp import SR
from sr.config import get_settings
from sr.providers.base import BandAdapterSpec, MusicGeneration, MusicGenerationProvider


class HttpMusicProvider(MusicGenerationProvider):
    name = "http"
    version = "http-music-0.1.0"
    trains_adapter = True

    def _base(self) -> str:
        url = getattr(get_settings(), "music_http_url", "") or ""
        if not url:
            raise RuntimeError("SR_MUSIC_HTTP_URL is not set")
        return url.rstrip("/")

    def generate(
        self, *, prompt: str, params: dict[str, Any], seed: int, adapter: dict[str, Any] | None
    ) -> MusicGeneration:
        import httpx  # noqa: PLC0415
        import soundfile as sf  # noqa: PLC0415

        r = httpx.post(
            f"{self._base()}/generate",
            json={"prompt": prompt, "seed": seed, "adapter": adapter, **params},
            timeout=1800,
        )
        r.raise_for_status()
        data, rate = sf.read(io.BytesIO(r.content), dtype="float32", always_2d=True)
        return MusicGeneration(
            audio=np.ascontiguousarray(data, dtype=np.float32),
            sample_rate=rate or SR,
            provider=self.name,
            provider_version=r.headers.get("x-provider-version", self.version),
            metadata={"prompt": prompt, "remote": self._base()},
        )

    def train_adapter(
        self, *, manifest: dict[str, Any], dna: dict[str, Any], params: dict[str, Any]
    ) -> BandAdapterSpec:
        import httpx  # noqa: PLC0415

        r = httpx.post(
            f"{self._base()}/train-adapter",
            json={"manifest": manifest, "dna": dna, "params": params},
            timeout=7200,
        )
        r.raise_for_status()
        return BandAdapterSpec(
            spec=r.json(), provider=self.name,
            provider_version=r.headers.get("x-provider-version", self.version),
            dataset_version=manifest.get("dataset_version", ""),
        )
