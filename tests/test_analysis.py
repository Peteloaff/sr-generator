"""Stage 6: reference-song analysis DSP."""

from __future__ import annotations

import numpy as np
import pytest

from sr.common import analysis
from sr.common.dsp import SR


def _track(bpm=120.0, notes=(220.0, 261.63, 329.63), seconds=24.0):
    t = np.arange(int(seconds * SR)) / SR
    chord = sum(0.12 * np.sin(2 * np.pi * f * t) for f in notes)
    bass = 0.18 * np.sin(2 * np.pi * notes[0] / 2 * t)
    drum = np.zeros_like(t)
    for b in np.arange(0, seconds, 60 / bpm):
        i = int(b * SR)
        rng = np.random.default_rng(int(b * 7))
        drum[i : i + 250] += np.exp(-np.linspace(0, 10, 250)) * rng.standard_normal(250) * 0.35
    return (chord + bass + drum * 0.5).astype(np.float32)


def test_bpm_is_close():
    assert analysis.estimate_bpm(_track(120.0)) == pytest.approx(120.0, abs=6)
    assert analysis.estimate_bpm(_track(96.0)) == pytest.approx(96.0, abs=6)


def test_key_detects_a_minor():
    a = analysis.estimate_key(_track(120.0, (220.0, 261.63, 329.63)))
    assert a["key"] == "A minor"
    assert a["confidence"] > 0.7


def test_analyze_bundle_is_complete_and_deterministic():
    x = _track(120.0)
    a = analysis.analyze(x)
    assert {
        "bpm", "key", "tuning", "loudness_dbfs", "energy_curve",
        "structure", "embedding", "duration",
    } <= a.keys()
    assert len(a["energy_curve"]) == 64
    assert len(a["embedding"]) == 34
    assert analysis.analyze(x) == a


def test_tuning_reports_standard_for_et_audio():
    a = analysis.estimate_tuning(_track(120.0))
    assert abs(a["cents"]) < 30
