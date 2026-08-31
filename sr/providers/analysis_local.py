"""LocalMirAnalysisProvider - real BPM/key/tuning/structure analysis (NumPy).

Approximate but deterministic. A real MIR stack (librosa / Essentia / a model)
implements the same ``analyze`` contract and registers as another provider.
"""

from __future__ import annotations

from pathlib import Path

from sr.common import analysis
from sr.common.dsp import SR, load_stereo
from sr.providers.base import AudioAnalysis, AudioAnalysisProvider


class LocalMirAnalysisProvider(AudioAnalysisProvider):
    name = "local_mir"
    version = "local-mir-0.6.0"

    def analyze(self, *, source_path: Path) -> AudioAnalysis:
        mono = load_stereo(Path(source_path)).mean(axis=1)
        return AudioAnalysis(
            analysis=analysis.analyze(mono, SR),
            provider=self.name,
            provider_version=self.version,
        )
