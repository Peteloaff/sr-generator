"""Provider contracts.

The application talks to these ABCs only - never to a concrete model. Swapping
ACE-Step for something else, or RVC for another voice tech, must not touch
anything outside sr/providers/. Every method returns a ``ProviderResult`` that
carries the provider version and enough metadata for job lineage.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ProviderResult:
    provider: str
    provider_version: str
    outputs: list[dict[str, Any]] = field(default_factory=list)  # {asset_type, file_path, ...}
    metadata: dict[str, Any] = field(default_factory=dict)
    logs: list[str] = field(default_factory=list)


class BaseProvider(abc.ABC):
    name: str = "base"
    version: str = "0.0.0"

    def _result(self, **kw: Any) -> ProviderResult:
        return ProviderResult(provider=self.name, provider_version=self.version, **kw)


class MusicGenerationProvider(BaseProvider):
    @abc.abstractmethod
    def generate(self, *, prompt: str, params: dict[str, Any], seed: int) -> ProviderResult: ...


class VoiceProvider(BaseProvider):
    @abc.abstractmethod
    def render(
        self, *, guide_asset: str | None, singer_ref: str, params: dict[str, Any], seed: int
    ) -> ProviderResult: ...


class StemSeparationProvider(BaseProvider):
    @abc.abstractmethod
    def separate(self, *, source_asset: str, params: dict[str, Any]) -> ProviderResult: ...


class AudioAnalysisProvider(BaseProvider):
    @abc.abstractmethod
    def analyze(self, *, source_asset: str) -> ProviderResult: ...


class MasteringProvider(BaseProvider):
    @abc.abstractmethod
    def master(self, *, mix_asset: str, params: dict[str, Any]) -> ProviderResult: ...


class TranscriptionProvider(BaseProvider):
    @abc.abstractmethod
    def transcribe(self, *, source_asset: str) -> ProviderResult: ...


PROVIDER_KINDS = {
    "music": MusicGenerationProvider,
    "voice": VoiceProvider,
    "stem": StemSeparationProvider,
    "analysis": AudioAnalysisProvider,
    "mastering": MasteringProvider,
    "transcription": TranscriptionProvider,
}
