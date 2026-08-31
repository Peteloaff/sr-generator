"""HttpAnalysisProvider - a remote MIR service.

``POST /analyze`` (multipart ``audio``) -> JSON analysis dict. Set
``SR_ANALYSIS_PROVIDER=http`` + ``SR_ANALYSIS_HTTP_URL``.
"""

from __future__ import annotations

from pathlib import Path

from sr.config import get_settings
from sr.providers.base import AudioAnalysis, AudioAnalysisProvider


class HttpAnalysisProvider(AudioAnalysisProvider):
    name = "http"
    version = "http-analysis-0.1.0"

    def analyze(self, *, source_path: Path) -> AudioAnalysis:
        import httpx  # noqa: PLC0415

        url = getattr(get_settings(), "analysis_http_url", "") or ""
        if not url:
            raise RuntimeError("SR_ANALYSIS_HTTP_URL is not set")
        r = httpx.post(
            f"{url.rstrip('/')}/analyze",
            files={"audio": (Path(source_path).name, Path(source_path).read_bytes())},
            timeout=600,
        )
        r.raise_for_status()
        return AudioAnalysis(
            analysis=r.json(),
            provider=self.name,
            provider_version=r.headers.get("x-provider-version", self.version),
        )
