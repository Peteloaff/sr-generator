"""Stage 7: the instrumental synth engine."""

from __future__ import annotations

import numpy as np
import pytest

from sr.common import musicgen
from sr.common.analysis import estimate_bpm


def test_generate_is_deterministic():
    a = musicgen.generate(bpm=128, key="E minor", seconds=6, seed=7)
    b = musicgen.generate(bpm=128, key="E minor", seconds=6, seed=7)
    assert np.array_equal(a["audio"], b["audio"])
    assert not np.array_equal(
        a["audio"], musicgen.generate(bpm=128, key="E minor", seconds=6, seed=8)["audio"]
    )


@pytest.mark.parametrize("bpm", [96, 120, 140])
def test_output_is_tempo_locked(bpm):
    out = musicgen.generate(bpm=bpm, key="A minor", seconds=12, seed=3)
    assert estimate_bpm(out["audio"].mean(axis=1)) == pytest.approx(bpm, abs=8)


def test_progression_is_diatonic_to_the_mode():
    minor = musicgen.generate(bpm=120, key="E minor", seconds=6, seed=1)["metadata"]
    major = musicgen.generate(bpm=120, key="C major", seconds=6, seed=1)["metadata"]
    assert minor["progression"] in musicgen._MINOR_PROG
    assert major["progression"] in musicgen._MAJOR_PROG
    assert minor["key"] == "E minor" and major["key"] == "C major"


def test_character_changes_the_sound():
    dark = musicgen.generate(
        bpm=120, key="C major", seconds=6, seed=1, character={"brightness": -0.9, "drum_busy": 0.1}
    )["audio"]
    bright = musicgen.generate(
        bpm=120, key="C major", seconds=6, seed=1, character={"brightness": 0.9, "drum_busy": 0.9}
    )["audio"]
    assert not np.allclose(dark, bright, atol=1e-3)


def test_shape_and_headroom():
    out = musicgen.generate(bpm=130, key="G major", seconds=4, seed=5)
    assert out["audio"].shape == (4 * musicgen.SR, 2)
    assert float(np.max(np.abs(out["audio"]))) <= 0.95
