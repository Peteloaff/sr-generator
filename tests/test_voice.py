"""Stage 3: voice analysis + conversion DSP."""

from __future__ import annotations

import numpy as np
import pytest

from sr.common import voice
from sr.common.dsp import SR


def _tone(f0=140.0, seconds=1.5):
    t = np.arange(int(seconds * SR)) / SR
    return (0.4 * np.sin(2 * np.pi * f0 * t) + 0.1 * np.sin(2 * np.pi * 3 * f0 * t)).astype(
        np.float32
    )


def test_estimate_f0_tracks_the_tone():
    assert voice.estimate_f0(_tone(120.0)) == pytest.approx(120.0, abs=6.0)
    assert voice.estimate_f0(_tone(240.0)) == pytest.approx(240.0, abs=10.0)


def test_analyze_returns_a_usable_profile():
    prof = voice.analyze(_tone(110.0))
    assert 90.0 < prof.median_f0 < 130.0
    assert -1.0 <= prof.brightness <= 1.0
    assert 0.0 <= prof.breathiness <= 1.0


def test_profile_dict_roundtrip():
    p = voice.VoiceProfile(median_f0=200.0, brightness=0.3)
    assert voice.VoiceProfile.from_dict(p.to_dict()) == p
    assert voice.VoiceProfile.from_dict({"median_f0": 200.0}).brightness == 0.0


def test_convert_preserves_length_and_is_deterministic():
    x = _tone(200.0, 2.0)
    low = voice.VoiceProfile(median_f0=110.0, brightness=-0.5)
    a = voice.convert(x, low, seed=1)
    b = voice.convert(x, low, seed=1)
    assert a.shape == x.shape
    assert np.array_equal(a, b)


def _centroid(x: np.ndarray) -> float:
    spec = np.abs(np.fft.rfft(x * np.hanning(len(x))))
    freqs = np.fft.rfftfreq(len(x), 1 / SR)
    return float((spec * freqs).sum() / (spec.sum() + 1e-9))


def test_different_profiles_give_different_voices():
    x = _tone(200.0, 2.0)
    dark = voice.convert(x, voice.VoiceProfile(median_f0=150.0, brightness=-0.8), seed=1)
    bright = voice.convert(x, voice.VoiceProfile(median_f0=150.0, brightness=0.8), seed=1)
    assert not np.allclose(dark, bright, atol=1e-3)
    assert _centroid(dark) < _centroid(bright)


def test_convert_keeps_signal_bounded():
    x = _tone(200.0, 1.5)
    out = voice.convert(x, voice.VoiceProfile(breathiness=1.0, roughness=1.0), seed=3)
    assert float(np.max(np.abs(out))) <= 1.0
