"""Stage 5: center-channel separation DSP."""

from __future__ import annotations

import numpy as np

from sr.common.dsp import SR
from sr.common.separation import separate_center
from sr.common.vocalfx import width_ratio


def _cover(seconds=3.0):
    t = np.arange(int(seconds * SR)) / SR
    vocal = 0.35 * np.sin(2 * np.pi * 262 * t)  # centre melody
    inst_l = 0.25 * np.sin(2 * np.pi * 110 * t)
    inst_r = 0.25 * np.sin(2 * np.pi * 110 * t + 0.7) + 0.1 * np.sin(2 * np.pi * 330 * t)
    return np.stack([vocal + inst_l, vocal + inst_r], axis=1).astype(np.float32)


def test_stems_reconstruct_the_mix():
    mix = _cover()
    parts = separate_center(mix)
    recon = parts["vocal"] + parts["instrumental"]
    assert np.allclose(recon, mix, atol=1e-4)


def test_vocal_is_more_centred_than_the_mix():
    mix = _cover()
    parts = separate_center(mix)
    assert width_ratio(parts["vocal"]) < width_ratio(mix)


def test_separation_is_deterministic():
    mix = _cover()
    a = separate_center(mix)
    b = separate_center(mix)
    assert np.array_equal(a["vocal"], b["vocal"])
    assert np.array_equal(a["instrumental"], b["instrumental"])
