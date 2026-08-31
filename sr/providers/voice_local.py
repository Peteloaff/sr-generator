"""LocalDspVoiceProvider - a real, dependency-free singing-voice conversion.

Not a neural model: it transforms the guide vocal itself (pitch to the target
register, STFT formant warp, spectral tilt, breath, drive) so the words are
preserved and each singer sounds distinct. A neural VoiceProvider implements the
same ``analyze`` / ``convert`` contract and is selected via ``SR_VOICE_PROVIDER``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from sr.common import voice
from sr.common.dsp import SR, load_stereo
from sr.providers.base import VoiceConversion, VoiceProvider


class LocalDspVoiceProvider(VoiceProvider):
    name = "local_dsp"
    version = "local-dsp-voice-0.3.0"
    trains = True

    def analyze(self, sample_paths: list[Path], *, singer_ref: str) -> dict[str, Any]:
        chunks: list[np.ndarray] = []
        for p in sample_paths:
            mono = load_stereo(Path(p)).mean(axis=1)
            chunks.append(mono[: SR * 20])  # cap each sample at 20s
        if not chunks:
            return voice.VoiceProfile().to_dict()
        mono = np.concatenate(chunks).astype(np.float32)
        return voice.analyze(mono, SR).to_dict()

    def convert(
        self, *, guide_path: Path, profile: dict[str, Any], params: dict[str, Any], seed: int
    ) -> VoiceConversion:
        mono = load_stereo(Path(guide_path)).mean(axis=1).astype(np.float32)
        prof = voice.VoiceProfile.from_dict(profile)
        out = voice.convert(
            mono, prof, guide_f0=params.get("guide_f0"), seed=seed, sr=SR
        )
        return VoiceConversion(
            samples=out,
            sample_rate=SR,
            provider=self.name,
            provider_version=self.version,
            metadata={"profile": prof.to_dict(), "guide_seconds": round(len(mono) / SR, 3)},
        )
