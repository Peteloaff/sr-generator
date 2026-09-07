"""Instrument-style analysis (pure NumPy, deterministic).

Given a separated instrument stem, estimate how the player plays it - register,
brightness, drive/distortion, attack (pick vs finger vs stick), how legato, how
busy, how dynamic, and (if a tempo is known) how syncopated and how much swing.
Approximate but reproducible: the same stem always yields the same profile.

The output feeds two places:
  * ``train_player`` stores it on the Player as a reusable named style
  * Stage 14 generation shapes each synth part by the assigned player's profile

A neural ``PlayerStyleProvider`` implements the same ``analyze`` contract.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np

from sr.common.dsp import SR, stft

_WIN, _HOP = 2048, 512


@dataclass(frozen=True)
class StyleProfile:
    role: str = "keys"
    register_hz: float = 440.0      # energy-weighted spectral centroid
    brightness: float = 0.0        # -1 dark .. +1 bright (spectral tilt)
    drive: float = 0.2            # 0 clean .. 1 heavily distorted / saturated
    attack: float = 0.5          # 0 soft (finger/pad) .. 1 sharp (pick/stick)
    sustain: float = 0.5        # 0 staccato .. 1 legato / held
    note_density: float = 2.0  # onsets per second
    busyness: float = 0.4     # note_density normalised for the role, 0..1
    dynamics: float = 0.5   # 0 squashed/compressed .. 1 very dynamic
    syncopation: float = 0.0  # 0 on-grid .. 1 very off-beat (needs a tempo)
    swing: float = 0.0       # 0 straight .. 1 hard-swung 8ths (needs a tempo)
    low_end: float = 0.3    # share of energy below ~250 Hz
    stereo_width: float = 0.2

    @classmethod
    def from_dict(cls, d: dict | None) -> StyleProfile:
        d = d or {}
        return cls(**{k: d[k] for k in cls.__dataclass_fields__ if k in d})

    def to_dict(self) -> dict:
        return {k: (round(v, 4) if isinstance(v, float) else v) for k, v in asdict(self).items()}


# role -> (min, max) note density we treat as 0..1 busyness
_DENSITY_RANGE = {
    "drums": (1.0, 9.0),
    "bass": (0.5, 4.0),
    "lead_guitar": (0.5, 6.0),
    "rhythm_guitar": (0.5, 5.0),
    "keys": (0.5, 5.0),
}


def _mono(stereo: np.ndarray) -> np.ndarray:
    if stereo.ndim == 1:
        return stereo.astype(np.float32)
    return stereo.mean(axis=1).astype(np.float32)


def _onset_env(mag: np.ndarray) -> np.ndarray:
    flux = np.maximum(np.diff(mag, axis=0, prepend=mag[:1]), 0.0).sum(axis=1)
    m = flux.max()
    return flux / m if m > 0 else flux


def _onset_frames(env: np.ndarray) -> np.ndarray:
    if env.size < 3:
        return np.zeros(0, dtype=int)
    thr = env.mean() + 0.6 * env.std()
    peaks = [
        i for i in range(1, len(env) - 1)
        if env[i] > thr and env[i] >= env[i - 1] and env[i] > env[i + 1]
    ]
    return np.asarray(peaks, dtype=int)


def _tilt(spec: np.ndarray, freqs: np.ndarray) -> tuple[float, float]:
    """(centroid_hz, brightness) from a mean magnitude spectrum."""
    total = float(spec.sum()) or 1.0
    centroid = float((spec * freqs).sum() / total)
    brightness = float(np.clip((centroid - 1500.0) / 1500.0, -1.0, 1.0))
    return centroid, brightness


def _drive(mono: np.ndarray, mag: np.ndarray) -> float:
    """Distortion / saturation estimate.

    Distorted sources are compressed (low crest factor), spectrally dense (energy
    spread across many bins rather than a few partials), and have persistent
    high-order harmonic energy.
    """
    if mono.size == 0:
        return 0.2
    rms = float(np.sqrt(np.mean(mono**2))) or 1e-6
    peak = float(np.max(np.abs(mono))) or 1e-6
    crest = peak / rms                       # ~1.4 square/distorted .. >6 clean transient
    crest_term = float(np.clip((6.0 - crest) / 4.5, 0.0, 1.0))
    if mag.shape[0]:
        frame = mag.mean(axis=0)
        frame = frame / (frame.sum() + 1e-9)
        flatness = float(np.exp(np.mean(np.log(frame + 1e-9))) / (np.mean(frame) + 1e-9))
    else:
        flatness = 0.0
    return float(np.clip(0.55 * crest_term + 0.45 * flatness, 0.0, 1.0))


def _attack_sustain(env: np.ndarray, onsets: np.ndarray) -> tuple[float, float]:
    if onsets.size == 0:
        return 0.5, 0.5
    rises, decays = [], []
    for o in onsets:
        pre = env[max(0, o - 3): o + 1]
        rise = float(env[o] - pre.min()) if pre.size else 0.0
        rises.append(rise)
        post = env[o: o + 12]
        if post.size > 2 and post[0] > 1e-6:
            decays.append(float(post.mean() / post[0]))
    attack = float(np.clip(np.mean(rises) * 2.2, 0.0, 1.0)) if rises else 0.5
    sustain = float(np.clip(np.mean(decays), 0.0, 1.0)) if decays else 0.5
    return attack, sustain


def _grid(onsets_sec: np.ndarray, bpm: float) -> tuple[float, float]:
    """(syncopation, swing) given onset times in seconds and a tempo."""
    if bpm <= 0 or onsets_sec.size < 4:
        return 0.0, 0.0
    eighth = 30.0 / bpm
    phase = np.mod(onsets_sec / eighth, 1.0)          # 0 = on an 8th, 0.5 = between
    off = np.minimum(phase, 1.0 - phase)
    off = np.maximum(off - 0.1, 0.0)                  # ignore sub-30ms timing wobble
    syncopation = float(np.clip(np.mean(off) * 6.0, 0.0, 1.0))
    step = np.mod(np.round(onsets_sec / eighth).astype(int), 2)
    on_beat = np.mod(onsets_sec[step == 0] / eighth, 1.0)
    off_beat = np.mod(onsets_sec[step == 1] / eighth, 1.0)
    if on_beat.size and off_beat.size:
        drift = float(np.median(np.where(off_beat > 0.5, off_beat - 1.0, off_beat)))
        swing = float(np.clip(abs(drift) * 3.0, 0.0, 1.0))
    else:
        swing = 0.0
    return syncopation, swing


def analyze(stem: np.ndarray, role: str, *, sr: int = SR, bpm: float = 0.0) -> StyleProfile:
    stereo = stem if stem.ndim == 2 else np.stack([stem, stem], axis=1)
    mono = _mono(stereo)
    if mono.size < _WIN * 2:
        return StyleProfile(role=role)

    seconds = mono.size / sr
    mag = np.abs(stft(mono, _WIN, _HOP))
    freqs = np.fft.rfftfreq(_WIN, 1.0 / sr)
    spec = mag.mean(axis=0)

    centroid, brightness = _tilt(spec, freqs)
    env = _onset_env(mag)
    onset_f = _onset_frames(env)
    onsets_sec = onset_f * (_HOP / sr)
    density = float(len(onset_f) / seconds) if seconds > 0 else 0.0

    lo, hi = _DENSITY_RANGE.get(role, (0.5, 5.0))
    busyness = float(np.clip((density - lo) / (hi - lo), 0.0, 1.0))

    attack, sustain = _attack_sustain(env, onset_f)
    drive = _drive(mono, mag)

    # dynamics: variability of short-window RMS
    w = max(1, int(0.1 * sr))
    n = mono.size // w
    dynamics = 0.5
    if n >= 4:
        rms = np.sqrt(np.mean(mono[: n * w].reshape(n, w) ** 2, axis=1))
        loud = rms[rms > rms.max() * 0.05]
        if loud.size:
            dynamics = float(np.clip((loud.std() / (loud.mean() + 1e-9)) * 1.6, 0.0, 1.0))

    low_end = float(spec[freqs < 250].sum() / (spec.sum() + 1e-9))

    if stereo.shape[1] == 2:
        lch, rch = stereo[:, 0], stereo[:, 1]
        denom = float(np.sqrt(np.mean(lch**2) * np.mean(rch**2))) or 1e-9
        corr = float(np.mean(lch * rch) / denom)
        width = float(np.clip((1.0 - corr) * 0.7, 0.0, 1.0))
    else:
        width = 0.0

    syncopation, swing = _grid(onsets_sec, bpm)

    return StyleProfile(
        role=role,
        register_hz=round(float(centroid), 1),
        brightness=round(brightness, 4),
        drive=round(drive, 4),
        attack=round(attack, 4),
        sustain=round(sustain, 4),
        note_density=round(density, 3),
        busyness=round(busyness, 4),
        dynamics=round(dynamics, 4),
        syncopation=round(syncopation, 4),
        swing=round(swing, 4),
        low_end=round(low_end, 4),
        stereo_width=round(width, 4),
    )


def blend(profiles: list[StyleProfile]) -> StyleProfile:
    """Average several per-sample profiles into one (register on a log scale)."""
    if not profiles:
        return StyleProfile()
    if len(profiles) == 1:
        return profiles[0]
    role = profiles[0].role
    keys = [k for k in StyleProfile.__dataclass_fields__ if k != "role"]
    out: dict[str, float] = {}
    for k in keys:
        vals = np.array([getattr(p, k) for p in profiles], dtype=float)
        if k == "register_hz":
            out[k] = float(np.exp(np.mean(np.log(np.clip(vals, 20.0, None)))))
        else:
            out[k] = float(np.mean(vals))
    return StyleProfile(role=role, **{k: round(v, 4) for k, v in out.items()})
