"""Center-channel source separation (pure NumPy, deterministic).

Lead vocals in most mixes sit in the phantom centre. This estimates a
soft-mask separation from the mid (L+R) and side (L-R) signals: a bin that is
loud in mid but quiet in side is probably voice; a bin loud in both is probably
music. Crude next to Demucs, but real and dependency-free - enough to lift a
usable guide vocal + instrumental out of a cover so the Stage 2/3 pipeline can
replace the vocal while keeping the melody.
"""

from __future__ import annotations

import numpy as np

from sr.common.dsp import SR, istft, stft

_WIN, _HOP = 2048, 512


def _band_weight(n_bins: int, sr: int, lo: float = 110.0, hi: float = 13000.0) -> np.ndarray:
    freqs = np.fft.rfftfreq(_WIN, 1.0 / sr)[:n_bins]
    w = np.ones(n_bins, dtype=np.float32)
    w *= 1.0 / (1.0 + (lo / np.maximum(freqs, 1.0)) ** 4)   # roll off below lo
    w *= 1.0 / (1.0 + (freqs / hi) ** 4)                    # roll off above hi
    return w


def separate_center(stereo: np.ndarray, *, sr: int = SR, strength: float = 1.4) -> dict:
    """Return {'vocal': (n,2), 'instrumental': (n,2)} float32."""
    stereo = np.ascontiguousarray(stereo, dtype=np.float32)
    n = stereo.shape[0]
    left = stereo[:, 0]
    right = stereo[:, 1]
    mid = 0.5 * (left + right)
    side = 0.5 * (left - right)

    M = stft(mid, _WIN, _HOP)
    S = stft(side, _WIN, _HOP)
    if M.shape[0] == 0:
        return {"vocal": np.zeros((n, 2), np.float32), "instrumental": stereo.copy()}

    band = _band_weight(M.shape[1], sr)
    am, as_ = np.abs(M), np.abs(S)
    mask = am / (am + strength * as_ + 1e-6)          # 1 -> pure centre, 0 -> stereo
    mask = np.clip(mask * band[None, :], 0.0, 1.0)

    vocal_mono = istft(M * mask, n, _WIN, _HOP)
    vocal = np.stack([vocal_mono, vocal_mono], axis=1).astype(np.float32)
    instrumental = (stereo - vocal).astype(np.float32)
    return {"vocal": vocal, "instrumental": instrumental}
