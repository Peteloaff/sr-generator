"""Deterministic guide-melody synthesis (pure NumPy).

A monophonic "la" line that outlines a section's key and follows a simple contour
shaped by section energy. Not a singing model - it is the guide melody the
VoiceProvider converts into each singer (Stage 3). Same (key, bpm, seconds, seed,
energy) -> identical audio, so a full-song generation is reproducible.
"""

from __future__ import annotations

import numpy as np

from sr.common.dsp import SR
from sr.common.seeds import derive_seed

_NOTES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
_MAJOR_SCALE = [0, 2, 4, 5, 7, 9, 11]
_MINOR_SCALE = [0, 2, 3, 5, 7, 8, 10]


def _tonic(key: str) -> tuple[int, str]:
    parts = (key or "C major").split()
    name = parts[0] if parts else "C"
    mode = "minor" if len(parts) > 1 and parts[1].lower().startswith("min") else "major"
    return (_NOTES.index(name) if name in _NOTES else 0), mode


def _midi_hz(midi: float) -> float:
    return 440.0 * 2.0 ** ((midi - 69.0) / 12.0)


def generate_guide(
    *, key: str, bpm: float, seconds: float, seed: int, energy: float = 0.6, sr: int = SR
) -> np.ndarray:
    """A mono float32 guide melody for one section."""
    tonic, mode = _tonic(key)
    scale = _MINOR_SCALE if mode == "minor" else _MAJOR_SCALE
    bpm = float(np.clip(bpm or 120.0, 50.0, 210.0))
    n = max(1, int(seconds * sr))
    beat = 60.0 / bpm
    note_beats = 0.5 if energy > 0.66 else 1.0
    note_len = max(1, int(note_beats * beat * sr))
    count = max(1, n // note_len)

    rng = np.random.default_rng(derive_seed(seed, "guide") & ((1 << 63) - 1))
    out = np.zeros(n, dtype=np.float32)
    degree = 0
    for i in range(count):
        degree = int(np.clip(degree + int(rng.integers(-2, 3)), -3, 7))
        if i == count - 1 or i % 4 == 3:
            degree = 0  # resolve phrases to the tonic
        pc = (tonic + scale[degree % 7]) % 12
        octave = 3 + (degree // 7)
        f = _midi_hz(12 * (octave + 1) + pc)

        s = i * note_len
        e = min(n, s + note_len)
        seg = e - s
        t = np.arange(seg) / sr
        vib = 1.0 + 0.015 * np.sin(2 * np.pi * 5.5 * t)
        tone = (
            0.5 * np.sin(2 * np.pi * f * vib * t)
            + 0.25 * np.sin(2 * np.pi * 2 * f * vib * t)
            + 0.12 * np.sin(2 * np.pi * 3 * f * vib * t)
        )
        env = np.ones(seg, dtype=np.float32)
        a = min(seg, int(0.02 * sr))
        r = min(seg, int(0.06 * sr))
        if a:
            env[:a] = np.linspace(0.0, 1.0, a)
        if r:
            env[seg - r :] = np.linspace(float(env[seg - r]) if seg - r >= 0 else 1.0, 0.0, r)
        am = 0.75 + 0.25 * np.clip(np.sin(2 * np.pi * 3.0 * t) ** 2, 0.0, 1.0)
        out[s:e] = (0.35 * tone * env * am).astype(np.float32)
    return out
