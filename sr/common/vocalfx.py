"""Vocal-stack processing hooks and A/B metrics (pure NumPy, deterministic).

Applied to a summed *role stem* (all takes of one vocal role). The goal of
Stage 4 is that a stack sounds produced, not copied: intervals + humanisation
make it wide, and a gentle de-ess / EQ / compressor chain glues it.

None of this is a mastering-grade plugin - it is honest, deterministic DSP that
audibly does its job and is measurable in tests.
"""

from __future__ import annotations

import numpy as np

from sr.common.dsp import SR


def stack_gain(count: int) -> float:
    """Sum-compensation for stacking near-correlated takes (~1/sqrt(n))."""
    return 1.0 / np.sqrt(max(1, count))


def _smooth(x: np.ndarray, window: int) -> np.ndarray:
    window = max(1, int(window))
    if window == 1:
        return x
    k = np.ones(window, dtype=np.float32) / window
    return np.convolve(x, k, mode="same").astype(np.float32)


def _fft_shelf_gain(freqs: np.ndarray, db: float, corner: float, kind: str) -> np.ndarray:
    if abs(db) < 1e-6:
        return np.ones_like(freqs)
    lin = 10.0 ** (db / 20.0)
    if kind == "low":
        w = 1.0 / (1.0 + (freqs / max(corner, 1.0)) ** 2)
    else:
        w = 1.0 / (1.0 + (max(corner, 1.0) / np.maximum(freqs, 1.0)) ** 2)
    return (1.0 + (lin - 1.0) * w).astype(np.float32)


def eq(
    x: np.ndarray,
    *,
    low_shelf_db: float = 0.0,
    low_freq: float = 180.0,
    high_shelf_db: float = 0.0,
    high_freq: float = 6000.0,
    presence_db: float = 0.0,
    presence_freq: float = 3000.0,
    presence_q: float = 1.0,
    sr: int = SR,
) -> np.ndarray:
    """Full-signal FFT EQ: two shelves + one presence bell. Gentle curves only."""
    n = x.shape[0]
    freqs = np.fft.rfftfreq(n, 1.0 / sr)
    gain = (
        _fft_shelf_gain(freqs, low_shelf_db, low_freq, "low")
        * _fft_shelf_gain(freqs, high_shelf_db, high_freq, "high")
    )
    if abs(presence_db) > 1e-6:
        bw = max(presence_freq / max(presence_q, 0.1), 1.0)
        bell = np.exp(-0.5 * ((freqs - presence_freq) / bw) ** 2)
        gain = gain * (1.0 + (10.0 ** (presence_db / 20.0) - 1.0) * bell)
    spec = np.fft.rfft(x, axis=0) * gain[:, None]
    return np.fft.irfft(spec, n=n, axis=0).astype(np.float32)


def deesser(
    x: np.ndarray, amount: float = 0.5, *, sr: int = SR, freq: float = 5500.0
) -> np.ndarray:
    """Duck sibilant energy above ``freq`` when it spikes. ``amount`` 0..1."""
    if amount <= 1e-3:
        return x
    n = x.shape[0]
    freqs = np.fft.rfftfreq(n, 1.0 / sr)
    hp_mask = (freqs >= freq).astype(np.float32)
    spec = np.fft.rfft(x, axis=0)
    hi = np.fft.irfft(spec * hp_mask[:, None], n=n, axis=0).astype(np.float32)
    lo = x - hi

    env = _smooth(np.abs(hi).mean(axis=1), int(sr * 0.003))
    hf_rms = float(np.sqrt(np.mean(hi**2))) + 1e-9
    over = np.clip(env / (hf_rms * 1.3) - 1.0, 0.0, 4.0)
    reduction = 1.0 - amount * 0.85 * (over / (1.0 + over))
    return (lo + hi * reduction[:, None]).astype(np.float32)


def compressor(
    x: np.ndarray,
    *,
    threshold_db: float = -18.0,
    ratio: float = 3.0,
    attack_ms: float = 10.0,
    release_ms: float = 120.0,
    makeup_db: float = 0.0,
    knee_db: float = 6.0,
    sr: int = SR,
) -> np.ndarray:
    """Soft-knee downward compressor with smoothed gain (deterministic)."""
    if ratio <= 1.0:
        return (x * 10.0 ** (makeup_db / 20.0)).astype(np.float32)
    mono = np.abs(x).mean(axis=1)
    env = _smooth(mono, int(sr * attack_ms / 1000.0))
    level_db = 20.0 * np.log10(np.maximum(env, 1e-6))

    over = level_db - threshold_db
    knee = max(knee_db, 1e-6)
    # soft knee: 0 below knee, quadratic in knee, linear above
    gr_db = np.where(
        over <= -knee / 2,
        0.0,
        np.where(
            over >= knee / 2,
            over * (1.0 - 1.0 / ratio),
            (1.0 - 1.0 / ratio) * (over + knee / 2) ** 2 / (2.0 * knee),
        ),
    )
    gr_db = _smooth(gr_db, int(sr * release_ms / 1000.0))
    gain = 10.0 ** ((makeup_db - gr_db) / 20.0)
    return (x * gain[:, None]).astype(np.float32)


_DISPATCH = {
    "deesser": lambda x, p, sr: deesser(x, float(p.get("amount", 0.5)), sr=sr,
                                        freq=float(p.get("freq", 5500.0))),
    "eq": lambda x, p, sr: eq(
        x, sr=sr,
        low_shelf_db=float(p.get("low_shelf_db", 0.0)),
        low_freq=float(p.get("low_freq", 180.0)),
        high_shelf_db=float(p.get("high_shelf_db", 0.0)),
        high_freq=float(p.get("high_freq", 6000.0)),
        presence_db=float(p.get("presence_db", 0.0)),
        presence_freq=float(p.get("presence_freq", 3000.0)),
        presence_q=float(p.get("presence_q", 1.0)),
    ),
    "compressor": lambda x, p, sr: compressor(
        x, sr=sr,
        threshold_db=float(p.get("threshold_db", -18.0)),
        ratio=float(p.get("ratio", 3.0)),
        attack_ms=float(p.get("attack_ms", 10.0)),
        release_ms=float(p.get("release_ms", 120.0)),
        makeup_db=float(p.get("makeup_db", 0.0)),
        knee_db=float(p.get("knee_db", 6.0)),
    ),
}

CHAIN_TYPES = tuple(_DISPATCH)


def apply_chain(
    x: np.ndarray, chain: list[dict] | None, *, sr: int = SR
) -> tuple[np.ndarray, list[str]]:
    log: list[str] = []
    if not chain:
        return x, log
    for step in chain:
        fx = _DISPATCH.get(step.get("type", ""))
        if fx is None:
            continue
        x = fx(x, step, sr)
        log.append(step["type"])
    return np.clip(x, -1.0, 1.0).astype(np.float32), log


# --- A/B metrics ------------------------------------------------------

def stereo_correlation(x: np.ndarray) -> float:
    if x.ndim != 2 or x.shape[1] != 2 or x.shape[0] < 2:
        return 1.0
    left, right = x[:, 0], x[:, 1]
    ls, rs = float(left.std()), float(right.std())
    if ls < 1e-9 or rs < 1e-9:
        return 1.0
    return float(np.mean((left - left.mean()) * (right - right.mean())) / (ls * rs))


def mid_side_rms(x: np.ndarray) -> tuple[float, float]:
    mid = (x[:, 0] + x[:, 1]) * 0.5
    side = (x[:, 0] - x[:, 1]) * 0.5
    rms = lambda a: float(np.sqrt(np.mean(a**2)) + 1e-12)  # noqa: E731
    return rms(mid), rms(side)


def width_ratio(x: np.ndarray) -> float:
    """side / mid RMS - 0 is mono, higher is wider."""
    mid, side = mid_side_rms(x)
    return side / mid


def mono_compat(x: np.ndarray) -> float:
    """RMS of the mono sum vs the mean channel RMS. ~1 healthy, ->0 = phase collapse."""
    mid, _ = mid_side_rms(x)
    chan = 0.5 * (
        float(np.sqrt(np.mean(x[:, 0] ** 2))) + float(np.sqrt(np.mean(x[:, 1] ** 2)))
    ) + 1e-12
    return mid / chan
