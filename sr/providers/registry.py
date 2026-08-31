"""Provider registry: map a ``(kind, name)`` to a concrete provider instance.

Selection is config-driven (``SR_MUSIC_PROVIDER`` etc). Stage 0 registers only
mock implementations; real adapters register here without touching call sites.
"""

from __future__ import annotations

from sr.config import get_settings
from sr.providers import base, mock

_REGISTRY: dict[tuple[str, str], type[base.BaseProvider]] = {
    ("music", "mock"): mock.MockMusicProvider,
    ("voice", "mock"): mock.MockVoiceProvider,
    ("stem", "mock"): mock.MockStemProvider,
    ("analysis", "mock"): mock.MockAnalysisProvider,
    ("mastering", "mock"): mock.MockMasteringProvider,
    ("transcription", "mock"): mock.MockTranscriptionProvider,
}

_CONFIG_KEY = {
    "music": "music_provider",
    "voice": "voice_provider",
    "stem": "stem_provider",
    "analysis": "analysis_provider",
    "mastering": "mastering_provider",
    "transcription": "transcription_provider",
}


def register(kind: str, name: str, cls: type[base.BaseProvider]) -> None:
    _REGISTRY[(kind, name)] = cls


def get_provider(kind: str, name: str | None = None) -> base.BaseProvider:
    if kind not in base.PROVIDER_KINDS:
        raise KeyError(f"unknown provider kind: {kind!r}")
    if name is None:
        name = getattr(get_settings(), _CONFIG_KEY[kind])
    try:
        return _REGISTRY[(kind, name)]()
    except KeyError as exc:
        raise KeyError(f"no provider registered for ({kind!r}, {name!r})") from exc


def available() -> list[str]:
    return [f"{k}:{n}" for (k, n) in sorted(_REGISTRY)]
