"""Stage 4: vocal-stack processing hooks + A/B metrics."""

from __future__ import annotations

import numpy as np
import pytest

from sr.common import vocalfx
from sr.common.dsp import SR


def _noise(seconds=1.0, seed=1):
    rng = np.random.default_rng(seed)
    x = rng.standard_normal((int(seconds * SR), 2)).astype(np.float32) * 0.2
    return x


def test_stack_gain_compensates_for_count():
    assert vocalfx.stack_gain(1) == pytest.approx(1.0)
    assert vocalfx.stack_gain(4) == pytest.approx(0.5)
    assert vocalfx.stack_gain(9) == pytest.approx(1 / 3)


def test_eq_shifts_the_spectrum():
    x = _noise(1.0)
    bright = vocalfx.eq(x, high_shelf_db=9.0, high_freq=4000.0)
    dark = vocalfx.eq(x, high_shelf_db=-9.0, high_freq=4000.0)

    def hf_energy(a):
        spec = np.abs(np.fft.rfft(a[:, 0]))
        freqs = np.fft.rfftfreq(a.shape[0], 1 / SR)
        return float(spec[freqs > 4000].sum())

    assert hf_energy(bright) > hf_energy(x) > hf_energy(dark)


def test_deesser_ducks_sibilant_peaks():
    t = np.arange(2 * SR) / SR
    body = 0.15 * np.sin(2 * np.pi * 200 * t)          # steady vocal body
    ess = 0.6 * np.sin(2 * np.pi * 7000 * t) * ((t % 0.5) < 0.06)  # periodic "sss" bursts
    sig = (body + ess).astype(np.float32)
    x = np.stack([sig, sig], axis=1)
    out = vocalfx.deesser(x, amount=0.9)

    def burst_peak(a):
        seg = a[int(0.5 * SR):int(0.56 * SR), 0]
        return float(np.max(np.abs(seg)))

    def body_rms(a):
        seg = a[int(0.2 * SR):int(0.45 * SR), 0]
        return float(np.sqrt(np.mean(seg**2)))

    assert burst_peak(out) < burst_peak(x) * 0.8   # sibilant burst is ducked
    assert body_rms(out) == pytest.approx(body_rms(x), rel=0.15)  # body is mostly left alone


def test_compressor_reduces_dynamic_range():
    t = np.arange(2 * SR) / SR
    env = np.where(t < 1.0, 0.1, 0.9).astype(np.float32)
    sig = (env * np.sin(2 * np.pi * 200 * t)).astype(np.float32)
    x = np.stack([sig, sig], axis=1)
    out = vocalfx.compressor(x, threshold_db=-20.0, ratio=6.0, makeup_db=0.0)

    def band_rms(a, lo, hi):
        return float(np.sqrt(np.mean(a[int(lo * SR):int(hi * SR), 0] ** 2)))

    quiet_in, loud_in = band_rms(x, 0.2, 0.8), band_rms(x, 1.2, 1.8)
    quiet_out, loud_out = band_rms(out, 0.2, 0.8), band_rms(out, 1.2, 1.8)
    assert (loud_out / quiet_out) < (loud_in / quiet_in)


def test_apply_chain_runs_steps_in_order():
    x = _noise(0.5)
    out, log = vocalfx.apply_chain(
        x, [{"type": "eq", "low_shelf_db": -3}, {"type": "compressor", "ratio": 2}]
    )
    assert log == ["eq", "compressor"]
    assert out.shape == x.shape
    assert float(np.max(np.abs(out))) <= 1.0


def test_metrics_separate_wide_from_mono():
    n = SR
    rng = np.random.default_rng(3)
    mono_sig = rng.standard_normal(n).astype(np.float32) * 0.3
    mono = np.stack([mono_sig, mono_sig], axis=1)
    wide = np.stack([mono_sig, np.roll(mono_sig, 40) + rng.standard_normal(n) * 0.1], axis=1)

    assert vocalfx.stereo_correlation(mono) == pytest.approx(1.0, abs=1e-3)
    assert vocalfx.stereo_correlation(wide) < 0.9
    assert vocalfx.width_ratio(wide) > vocalfx.width_ratio(mono)
    assert vocalfx.mono_compat(mono) == pytest.approx(1.0, abs=1e-3)
