"""HttpVoiceProvider - calls a remote/local GPU voice-model service.

Not wired into tests (no service to talk to) but concrete, so the "GPU workers
optionally local or remote" story is real: point ``SR_VOICE_HTTP_URL`` at a
service exposing ``POST /analyze`` and ``POST /convert`` and set
``SR_VOICE_PROVIDER=http``.
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any

import numpy as np

from sr.common.dsp import SR
from sr.config import get_settings
from sr.providers.base import VoiceConversion, VoiceProvider


class HttpVoiceProvider(VoiceProvider):
    name = "http"
    version = "http-voice-0.1.0"
    trains = True

    def _base(self) -> str:
        url = getattr(get_settings(), "voice_http_url", "") or ""
        if not url:
            raise RuntimeError("SR_VOICE_HTTP_URL is not set")
        return url.rstrip("/")

    def analyze(self, sample_paths: list[Path], *, singer_ref: str) -> dict[str, Any]:
        import httpx  # noqa: PLC0415 - optional dependency, only when this provider is used

        files = [("samples", (Path(p).name, Path(p).read_bytes())) for p in sample_paths]
        r = httpx.post(
            f"{self._base()}/analyze", data={"singer_ref": singer_ref}, files=files, timeout=600
        )
        r.raise_for_status()
        return r.json()

    def convert(
        self, *, guide_path: Path, profile: dict[str, Any], params: dict[str, Any], seed: int
    ) -> VoiceConversion:
        import httpx  # noqa: PLC0415
        import soundfile as sf

        r = httpx.post(
            f"{self._base()}/convert",
            data={"profile": __import__("json").dumps(profile), "seed": str(seed)},
            files={"guide": (Path(guide_path).name, Path(guide_path).read_bytes())},
            timeout=1200,
        )
        r.raise_for_status()
        data, rate = sf.read(io.BytesIO(r.content), dtype="float32", always_2d=True)
        mono = data.mean(axis=1)
        return VoiceConversion(
            samples=mono.astype(np.float32),
            sample_rate=rate or SR,
            provider=self.name,
            provider_version=r.headers.get("x-provider-version", self.version),
            metadata={"remote": self._base()},
        )
