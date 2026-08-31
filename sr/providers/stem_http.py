"""HttpStemProvider - a Demucs-class separator behind an HTTP service.

Point ``SR_STEM_HTTP_URL`` at a service with ``POST /separate`` (multipart
``audio`` -> a multipart or zip of named WAV stems) and set
``SR_STEM_PROVIDER=http``.
"""

from __future__ import annotations

import io
import zipfile
from pathlib import Path
from typing import Any

import numpy as np

from sr.common.dsp import SR
from sr.config import get_settings
from sr.providers.base import StemSeparation, StemSeparationProvider


class HttpStemProvider(StemSeparationProvider):
    name = "http"
    version = "http-stem-0.1.0"
    produces = ("stem_lead_vocal", "stem_drums", "stem_bass", "stem_instrumental")

    def separate(self, *, source_path: Path, params: dict[str, Any]) -> StemSeparation:
        import httpx  # noqa: PLC0415
        import soundfile as sf  # noqa: PLC0415

        url = getattr(get_settings(), "stem_http_url", "") or ""
        if not url:
            raise RuntimeError("SR_STEM_HTTP_URL is not set")
        r = httpx.post(
            f"{url.rstrip('/')}/separate",
            files={"audio": (Path(source_path).name, Path(source_path).read_bytes())},
            timeout=1800,
        )
        r.raise_for_status()
        stems: dict[str, np.ndarray] = {}
        with zipfile.ZipFile(io.BytesIO(r.content)) as zf:
            for info in zf.infolist():
                data, _ = sf.read(io.BytesIO(zf.read(info)), dtype="float32", always_2d=True)
                key = f"stem_{Path(info.filename).stem}".replace("stem_stem_", "stem_")
                stems[key] = data
        return StemSeparation(
            stems=stems, sample_rate=SR, provider=self.name,
            provider_version=r.headers.get("x-provider-version", self.version),
        )
