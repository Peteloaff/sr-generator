"""BandSplitStemProvider - dependency-free 5-way split (fallback / CI).

A rough frequency + transient split into drums / bass / guitar / keys / vocal.
It exists so the player-style pipeline and its tests run everywhere; for real
per-instrument isolation install the ``separation`` extra and use
``SR_MULTISTEM_PROVIDER=demucs`` (the default).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from sr.common.dsp import SR, istft, load_stereo, stft
from sr.common.separation import separate_center
from sr.providers.base import StemSeparation, StemSeparationProvider

_WIN, _HOP = 2048, 512


def _band(mono: np.ndarray, sr: int, lo: float, hi: float) -> np.ndarray:
    spec = stft(mono, _WIN, _HOP)
    if spec.shape[0] == 0:
        return np.zeros_like(mono)
    freqs = np.fft.rfftfreq(_WIN, 1.0 / sr)
    mask = ((freqs >= lo) & (freqs < hi)).astype(np.float32)
    return istft(spec * mask[None, :], len(mono), _WIN, _HOP)


def _transient(mono: np.ndarray, sr: int) -> np.ndarray:
    """Percussive component: bins whose magnitude jumps frame-to-frame."""
    spec = stft(mono, _WIN, _HOP)
    if spec.shape[0] == 0:
        return np.zeros_like(mono)
    mag = np.abs(spec)
    flux = np.maximum(np.diff(mag, axis=0, prepend=mag[:1]), 0.0)
    gate = flux / (mag + 1e-6)
    return istft(spec * np.clip(gate * 2.0, 0.0, 1.0), len(mono), _WIN, _HOP)


class BandSplitStemProvider(StemSeparationProvider):
    name = "bandsplit"
    version = "bandsplit-0.13.0"
    produces = ("stem_drums", "stem_bass", "stem_guitar", "stem_keys", "stem_vocal")

    def separate(self, *, source_path: Path, params: dict[str, Any]) -> StemSeparation:
        stereo = load_stereo(Path(source_path))
        n = stereo.shape[0]
        parts = separate_center(stereo, sr=SR)
        vocal = parts["vocal"]
        instr = parts["instrumental"]
        mono = instr.mean(axis=1)

        trans = _transient(mono, SR)
        drums = trans + _band(mono - trans, SR, 20.0, 120.0) * 0.4
        detrans = mono - trans
        bass = _band(detrans, SR, 20.0, 200.0)
        mid = _band(detrans, SR, 200.0, 6000.0)
        # split the mid band: brighter half -> guitar, smoother half -> keys
        bright = mid - np.concatenate([[0.0], mid[:-1]])  # crude HF emphasis
        guitar = 0.6 * mid + 0.5 * bright
        keys = 0.5 * mid - 0.5 * bright

        def st(x: np.ndarray) -> np.ndarray:
            x = x[:n] if len(x) >= n else np.pad(x, (0, n - len(x)))
            return np.stack([x, x], axis=1).astype(np.float32)

        return StemSeparation(
            stems={
                "stem_drums": st(drums),
                "stem_bass": st(bass),
                "stem_guitar": st(guitar),
                "stem_keys": st(keys),
                "stem_vocal": vocal,
            },
            sample_rate=SR,
            provider=self.name,
            provider_version=self.version,
            metadata={"frames": int(n), "approximate": True},
        )
