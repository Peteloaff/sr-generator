"""Provider contracts.

The application talks to these ABCs only - never to a concrete model. Swapping
ACE-Step for something else, or RVC for another voice tech, must not touch
anything outside sr/providers/. Every method returns a ``ProviderResult`` that
carries the provider version and enough metadata for job lineage.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import numpy as np


@dataclass
class ProviderResult:
    provider: str
    provider_version: str
    outputs: list[dict[str, Any]] = field(default_factory=list)  # {asset_type, file_path, ...}
    metadata: dict[str, Any] = field(default_factory=dict)
    logs: list[str] = field(default_factory=list)


@dataclass
class VoiceConversion:
    """A converted guide vocal, returned as raw mono audio so the caller owns
    caching + file writing (local providers synthesise, remote ones fetch)."""

    samples: np.ndarray  # mono float32
    sample_rate: int
    provider: str
    provider_version: str
    metadata: dict[str, Any] = field(default_factory=dict)


class BaseProvider(abc.ABC):
    name: str = "base"
    version: str = "0.0.0"

    def _result(self, **kw: Any) -> ProviderResult:
        return ProviderResult(provider=self.name, provider_version=self.version, **kw)


class MusicGenerationProvider(BaseProvider):
    @abc.abstractmethod
    def generate(self, *, prompt: str, params: dict[str, Any], seed: int) -> ProviderResult: ...


class VoiceProvider(BaseProvider):
    """Renders / converts a guide vocal into a chosen singer identity while
    preserving melody, timing, and lyrics. A neural model (RVC, so-vits-svc,
    DiffSinger, ...) implements this same interface - locally or as an HTTP
    service to a GPU worker."""

    #: does this provider learn a model from samples, or only apply a profile?
    trains: bool = False

    @abc.abstractmethod
    def analyze(self, sample_paths: list[Path], *, singer_ref: str) -> dict[str, Any]:
        """Derive a voice profile / model descriptor from training samples."""

    @abc.abstractmethod
    def convert(
        self,
        *,
        guide_path: Path,
        profile: dict[str, Any],
        params: dict[str, Any],
        seed: int,
    ) -> VoiceConversion:
        """Convert one guide vocal toward the given voice profile."""


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
