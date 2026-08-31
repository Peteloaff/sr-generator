"""Stage 2: DSP primitives are length-preserving and deterministic."""

from __future__ import annotations

import numpy as np
import pytest

from sr.common import dsp


def _tone(seconds=1.0, freq=220.0):
    t = np.arange(int(seconds * dsp.SR)) / dsp.SR
    return (0.3 * np.sin(2 * np.pi * freq * t)).astype(np.float32)


def test_gain_db_is_multiplicative():
    x = np.ones((10, 2), dtype=np.float32)
    assert np.allclose(dsp.gain_db(x, -6.0206), 0.5, atol=1e-3)


def test_pan_is_equal_power():
    mono = np.ones(100, dtype=np.float32)
    centre = dsp.pan_mono(mono, 0.0)
    assert np.allclose(centre[:, 0] ** 2 + centre[:, 1] ** 2, 1.0, atol=1e-4)
    left = dsp.pan_mono(mono, -100.0)
    assert left[0, 0] > 0.99 and left[0, 1] < 0.01


def test_time_offset_preserves_length():
    x = np.ones((dsp.SR, 2), dtype=np.float32)
    for ms in (-50.0, -5.0, 0.0, 5.0, 50.0):
        assert dsp.time_offset(x, ms).shape == x.shape
    shifted = dsp.time_offset(x, 10.0)
    assert np.all(shifted[: int(0.01 * dsp.SR)] == 0.0)


def test_pitch_shift_preserves_length_and_is_deterministic():
    x = np.stack([_tone(), _tone()], axis=1)
    a = dsp.pitch_shift_cents(x, 12.0)
    b = dsp.pitch_shift_cents(x, 12.0)
    assert a.shape == x.shape
    assert np.array_equal(a, b)
    assert not np.array_equal(dsp.pitch_shift_cents(x, 0.0), a)


def test_sum_and_fit_length():
    a = np.ones((100, 2), dtype=np.float32)
    b = np.ones((50, 2), dtype=np.float32)
    out = dsp.sum_stereo([a, b], 100)
    assert out.shape == (100, 2)
    assert out[0, 0] == 2.0 and out[75, 0] == 1.0


def test_peak_normalize_only_when_hot():
    quiet = np.full((10, 2), 0.5, dtype=np.float32)
    same, g = dsp.peak_normalize(quiet)
    assert g == 0.0 and np.array_equal(same, quiet)
    hot = np.full((10, 2), 2.0, dtype=np.float32)
    norm, g = dsp.peak_normalize(hot, ceiling=0.98)
    assert float(np.max(np.abs(norm))) == pytest.approx(0.98, abs=1e-4)
    assert g < 0
