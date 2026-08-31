"""Deterministic placeholder 'vocal' synthesis for Stage 2.

When a singer has no uploaded take for a section, the layering engine needs
*something* to render so the pipeline can be proven. This makes a distinct,
non-silent, fully deterministic tone per singer (fundamental + harmonics +
syllable-rate amplitude envelope + light vibrato). Stage 3 replaces this with a
real VoiceProvider.
"""

from __future__ import annotations

import hashlib

import numpy as np

from sr.common.dsp import SR


def _hash_float(text: str, lo: float, hi: float) -> float:
    h = int.from_bytes(hashlib.blake2b(text.encode(), digest_size=8).digest(), "big")
    return lo + (h / float((1 << 64) - 1)) * (hi - lo)


def mock_singer_take(singer_id: str, section_id: str, seconds: float, seed: int) -> np.ndarray:
    """Return a mono float32 signal shaped ``(n,)`` in roughly [-0.5, 0.5]."""
    n = max(1, int(round(seconds * SR)))
    t = np.arange(n, dtype=np.float64) / SR

    f0 = _hash_float(f"{singer_id}:f0", 110.0, 240.0)  # per-singer fundamental
    vib_rate = _hash_float(f"{singer_id}:vib", 4.5, 6.5)
    vib_depth = _hash_float(f"{singer_id}:vibd", 0.002, 0.010)
    syllable = _hash_float(f"{section_id}:syl", 2.0, 3.5)  # per-section rhythm

    vib = 1.0 + vib_depth * np.sin(2 * np.pi * vib_rate * t)
    phase = 2 * np.pi * f0 * np.cumsum(vib) / SR

    tone = (
        1.00 * np.sin(phase)
        + 0.45 * np.sin(2 * phase)
        + 0.22 * np.sin(3 * phase)
        + 0.11 * np.sin(4 * phase)
    )

    env = 0.35 + 0.65 * np.clip(np.sin(2 * np.pi * syllable * t) ** 2, 0.0, 1.0)
    attack = np.clip(t / 0.02, 0.0, 1.0)
    release = np.clip((seconds - t) / 0.05, 0.0, 1.0)

    sig = tone * env * attack * release
    sig *= 0.4 / max(float(np.max(np.abs(sig))), 1e-9)
    # a whisper of deterministic noise so it is not a pure tone
    rng = np.random.default_rng(seed & ((1 << 63) - 1))
    sig += 0.01 * rng.standard_normal(n)
    return sig.astype(np.float32)
