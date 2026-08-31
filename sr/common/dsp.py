"""Deterministic audio DSP primitives (pure NumPy).

Everything works on float32 stereo arrays shaped ``(n_frames, 2)`` at a fixed
sample rate. Operations are pure and order-stable so a render is byte-identical
given the same inputs.

Stage 2 note: pitch shift is resample-based (it also moves formants) and formant
shift is a light one-pole tilt. Both are placeholders for a real pitch/formant
provider in a later stage - good enough to prove the layering pipeline.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import soundfile as sf

SR = 44100
_EPS = 1e-9


def load_stereo(path: Path, sr: int = SR) -> np.ndarray:
    data, file_sr = sf.read(str(path), dtype="float32", always_2d=True)
    if file_sr != sr:
        data = resample(data, int(round(data.shape[0] * sr / file_sr)))
    if data.shape[1] == 1:
        data = np.repeat(data, 2, axis=1)
    elif data.shape[1] > 2:
        data = data[:, :2]
    return np.ascontiguousarray(data, dtype=np.float32)


def save_wav(path: Path, x: np.ndarray, sr: int = SR) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(path), np.clip(x, -1.0, 1.0).astype(np.float32), sr, subtype="PCM_16")


def resample(x: np.ndarray, target_len: int) -> np.ndarray:
    if target_len <= 0:
        return np.zeros((0, x.shape[1]), dtype=np.float32)
    if target_len == x.shape[0]:
        return x
    src = np.linspace(0.0, 1.0, x.shape[0], dtype=np.float64)
    dst = np.linspace(0.0, 1.0, target_len, dtype=np.float64)
    return np.stack([np.interp(dst, src, x[:, c]) for c in range(x.shape[1])], axis=1).astype(
        np.float32
    )


def fit_length(x: np.ndarray, n: int) -> np.ndarray:
    """Truncate or zero-pad (at the end) to exactly ``n`` frames."""
    if x.shape[0] == n:
        return x
    if x.shape[0] > n:
        return x[:n]
    pad = np.zeros((n - x.shape[0], x.shape[1]), dtype=np.float32)
    return np.concatenate([x, pad], axis=0)


def gain_db(x: np.ndarray, db: float) -> np.ndarray:
    return (x * (10.0 ** (db / 20.0))).astype(np.float32)


def pan_mono(mono: np.ndarray, pan: float) -> np.ndarray:
    """Place a mono signal in the stereo field with an equal-power law.

    ``pan`` in [-100, 100]: -100 hard left, 0 centre, 100 hard right.
    """
    theta = (np.clip(pan, -100.0, 100.0) + 100.0) / 200.0 * (np.pi / 2.0)
    left = float(np.cos(theta))
    right = float(np.sin(theta))
    return np.stack([mono * left, mono * right], axis=1).astype(np.float32)


def time_offset(x: np.ndarray, ms: float, sr: int = SR) -> np.ndarray:
    """Shift by +/- milliseconds, preserving total length."""
    n = int(round(ms / 1000.0 * sr))
    if n == 0:
        return x
    if n > 0:
        return np.concatenate([np.zeros((n, x.shape[1]), dtype=np.float32), x], axis=0)[
            : x.shape[0]
        ]
    dropped = x[-n:]
    pad = np.zeros((-n, x.shape[1]), dtype=np.float32)
    return np.concatenate([dropped, pad], axis=0)


def pitch_shift_cents(x: np.ndarray, cents: float, sr: int = SR) -> np.ndarray:
    if abs(cents) < _EPS:
        return x
    ratio = 2.0 ** (cents / 1200.0)
    shifted = resample(x, int(round(x.shape[0] / ratio)))
    return fit_length(shifted, x.shape[0])


def formant_tilt(x: np.ndarray, amount: float) -> np.ndarray:
    """Very light spectral tilt as a stand-in for formant shifting.

    ``amount`` roughly in [-100, 100]; positive brightens, negative darkens.
    """
    if abs(amount) < _EPS:
        return x
    a = float(np.clip(amount / 100.0, -0.9, 0.9)) * 0.35
    diff = np.zeros_like(x)
    diff[1:] = x[1:] - x[:-1]  # first-difference = high-frequency content
    return (x + a * diff).astype(np.float32)


def sum_stereo(parts: list[np.ndarray], n: int) -> np.ndarray:
    acc = np.zeros((n, 2), dtype=np.float32)
    for p in parts:
        acc += fit_length(p, n)
    return acc


def peak_normalize(x: np.ndarray, ceiling: float = 0.98) -> tuple[np.ndarray, float]:
    peak = float(np.max(np.abs(x))) if x.size else 0.0
    if peak <= ceiling or peak < _EPS:
        return x, 0.0
    scale = ceiling / peak
    return (x * scale).astype(np.float32), 20.0 * float(np.log10(scale))


def rms_dbfs(x: np.ndarray) -> float:
    if not x.size:
        return -120.0
    rms = float(np.sqrt(np.mean(np.square(x, dtype=np.float64))))
    return 20.0 * float(np.log10(max(rms, _EPS)))


def stft(x: np.ndarray, win: int = 2048, hop: int = 512) -> np.ndarray:
    """Mono STFT -> (n_frames, n_bins) complex."""
    w = np.hanning(win).astype(np.float32)
    n = 1 + max(0, (len(x) - win) // hop)
    if n <= 0:
        return np.zeros((0, win // 2 + 1), dtype=complex)
    return np.stack([np.fft.rfft(x[i * hop : i * hop + win] * w) for i in range(n)])


def istft(frames: np.ndarray, length: int, win: int = 2048, hop: int = 512) -> np.ndarray:
    w = np.hanning(win).astype(np.float32)
    out = np.zeros(length + win, dtype=np.float32)
    norm = np.zeros(length + win, dtype=np.float32)
    for i, spec in enumerate(frames):
        frame = np.fft.irfft(spec, n=win).astype(np.float32) * w
        s = i * hop
        out[s : s + win] += frame
        norm[s : s + win] += w * w
    return (out / np.maximum(norm, 1e-6))[:length]
