"""Voice analysis and conversion DSP (pure NumPy).

This is a real transformation of a guide vocal - pitch to the target register,
STFT formant warp, spectral tilt, breath, and drive - so converted takes are
intelligible (the words survive) and audibly distinct per singer. It is a
placeholder for a neural VoiceProvider, not a competitor to one; the contract in
sr/providers/base.py is what a real model plugs into.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np

from sr.common.dsp import SR, fit_length

_WIN = 2048
_HOP = 512


@dataclass(frozen=True)
class VoiceProfile:
    median_f0: float = 180.0          # Hz, the singer's typical pitch
    formant_semitones: float = 0.0    # + = smaller vocal tract / brighter vowels
    brightness: float = 0.0           # -1 dark .. +1 bright (spectral tilt)
    breathiness: float = 0.0          # 0 .. 1 (added air)
    roughness: float = 0.0            # 0 .. 1 (drive / grit)

    @classmethod
    def from_dict(cls, d: dict | None) -> VoiceProfile:
        d = d or {}
        f = {k: d[k] for k in cls.__dataclass_fields__ if k in d}
        return cls(**f)

    def to_dict(self) -> dict:
        return asdict(self)


# --- analysis ------------------------------------------------------------

def estimate_f0(mono: np.ndarray, sr: int = SR, fmin: float = 70.0, fmax: float = 500.0) -> float:
    """Median fundamental over voiced frames (autocorrelation). 0.0 if unvoiced."""
    win = int(sr * 0.045)
    hop = win // 2
    lo, hi = int(sr / fmax), int(sr / fmin)
    vals: list[float] = []
    for start in range(0, max(1, len(mono) - win), hop):
        frame = mono[start : start + win]
        if float(np.sqrt(np.mean(frame**2))) < 0.01:
            continue
        frame = frame - frame.mean()
        corr = np.correlate(frame, frame, "full")[win - 1 :]
        if corr[0] <= 0:
            continue
        seg = corr[lo:hi]
        if seg.size == 0:
            continue
        lag = lo + int(np.argmax(seg))
        if corr[lag] / corr[0] > 0.3:
            vals.append(sr / lag)
    return float(np.median(vals)) if vals else 0.0


def analyze(mono: np.ndarray, sr: int = SR) -> VoiceProfile:
    mono = mono.astype(np.float32)
    f0 = estimate_f0(mono, sr) or 180.0

    spec = np.abs(np.fft.rfft(mono * np.hanning(len(mono)))) if len(mono) > 16 else np.array([1.0])
    freqs = np.fft.rfftfreq(len(mono), 1 / sr) if len(mono) > 16 else np.array([0.0])
    total = float(spec.sum()) or 1.0
    centroid = float((spec * freqs).sum() / total)
    hf_ratio = float(spec[freqs > 4000].sum() / total)

    brightness = float(np.clip((centroid - 1800.0) / 1800.0, -1.0, 1.0))
    breathiness = float(np.clip(hf_ratio * 4.0, 0.0, 1.0))
    # crude tract-size hint from how high the centroid sits above f0
    formant = float(np.clip(np.log2(max(centroid, 1.0) / max(f0 * 8.0, 1.0)) * 2.0, -4.0, 4.0))
    flat = float(np.exp(np.mean(np.log(spec + 1e-9))) / (spec.mean() + 1e-9))
    roughness = float(np.clip(flat * 1.5, 0.0, 0.6))

    return VoiceProfile(
        median_f0=round(f0, 2),
        formant_semitones=round(formant, 2),
        brightness=round(brightness, 3),
        breathiness=round(breathiness, 3),
        roughness=round(roughness, 3),
    )


# --- conversion --------------------------------------------------------

def _stft(x: np.ndarray) -> np.ndarray:
    w = np.hanning(_WIN).astype(np.float32)
    n = 1 + max(0, (len(x) - _WIN) // _HOP)
    return np.stack(
        [np.fft.rfft(x[i * _HOP : i * _HOP + _WIN] * w) for i in range(n)]
    ) if n else np.zeros((0, _WIN // 2 + 1), dtype=complex)


def _istft(frames: np.ndarray, length: int) -> np.ndarray:
    w = np.hanning(_WIN).astype(np.float32)
    out = np.zeros(length + _WIN, dtype=np.float32)
    norm = np.zeros(length + _WIN, dtype=np.float32)
    for i, spec in enumerate(frames):
        frame = np.fft.irfft(spec, n=_WIN).astype(np.float32) * w
        s = i * _HOP
        out[s : s + _WIN] += frame
        norm[s : s + _WIN] += w * w
    return (out / np.maximum(norm, 1e-6))[:length]


def _pitch_shift(x: np.ndarray, semitones: float) -> np.ndarray:
    if abs(semitones) < 1e-3:
        return x
    ratio = 2.0 ** (semitones / 12.0)
    idx = np.arange(0, len(x), 1.0 / ratio)
    idx = idx[idx < len(x) - 1]
    shifted = np.interp(idx, np.arange(len(x)), x).astype(np.float32)
    return fit_length(shifted.reshape(-1, 1), len(x))[:, 0]


def convert(
    mono: np.ndarray,
    profile: VoiceProfile,
    *,
    guide_f0: float | None = None,
    seed: int = 0,
    sr: int = SR,
    max_pitch_semitones: float = 7.0,
) -> np.ndarray:
    """Convert a mono guide vocal toward ``profile``. Returns mono, same length."""
    x = np.ascontiguousarray(mono, dtype=np.float32)
    if x.size < _WIN:
        return x

    # 1. pitch: move the guide toward the singer's register
    g_f0 = guide_f0 if guide_f0 and guide_f0 > 0 else estimate_f0(x, sr)
    if g_f0 > 0 and profile.median_f0 > 0:
        want = 12.0 * np.log2(profile.median_f0 / g_f0)
    else:
        want = profile.formant_semitones * 0.5
    pitch_semis = float(np.clip(want, -max_pitch_semitones, max_pitch_semitones))
    pitch_ratio = 2.0 ** (pitch_semis / 12.0)
    x = _pitch_shift(x, pitch_semis)

    # 2. spectral stage: net formant warp + brightness tilt
    frames = _stft(x)
    if frames.shape[0]:
        nb = frames.shape[1]
        idx = np.arange(nb)
        warp = (2.0 ** (profile.formant_semitones / 12.0)) / pitch_ratio
        src = np.clip(idx / max(warp, 1e-3), 0, nb - 1)
        nyq = sr / 2.0
        f = np.fft.rfftfreq(_WIN, 1 / sr)
        tilt = np.clip(1.0 + profile.brightness * 0.8 * (2.0 * f / nyq - 1.0), 0.2, 3.0)
        out = np.empty_like(frames)
        for i, spec in enumerate(frames):
            mag = np.interp(src, idx, np.abs(spec))
            out[i] = mag * tilt * np.exp(1j * np.angle(spec))
        x = _istft(out, len(x))

    # 3. breath: shaped noise following the amplitude envelope
    if profile.breathiness > 1e-3:
        rng = np.random.default_rng(seed & ((1 << 63) - 1))
        noise = rng.standard_normal(len(x)).astype(np.float32)
        env = np.abs(x)
        env = np.convolve(env, np.ones(256, dtype=np.float32) / 256.0, "same")
        x = x + profile.breathiness * 0.08 * noise * env

    # 4. roughness: gentle drive
    if profile.roughness > 1e-3:
        d = 1.0 + profile.roughness * 3.0
        x = ((1.0 - profile.roughness * 0.4) * x
             + profile.roughness * 0.4 * np.tanh(d * x) / np.tanh(d)).astype(np.float32)

    peak = float(np.max(np.abs(x))) or 1.0
    if peak > 0.99:
        x = x * (0.99 / peak)
    return x.astype(np.float32)
