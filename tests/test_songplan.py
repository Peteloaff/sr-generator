"""Stage 8: the deterministic song planner."""

from __future__ import annotations

from sr.services import songplan


def test_plan_is_deterministic_and_seed_sensitive():
    a = songplan.plan_song(prompt="midnight drive", seed=7)
    b = songplan.plan_song(prompt="midnight drive", seed=7)
    c = songplan.plan_song(prompt="midnight drive", seed=8)
    assert a == b
    a_types = [s["type"] for s in a["sections"]]
    c_types = [s["type"] for s in c["sections"]]
    assert a_types != c_types or a["key"] != c["key"]


def test_sections_are_contiguous_and_energy_bounded():
    plan = songplan.plan_song(prompt="loud fast song about the sea", seed=3, bpm=140)
    secs = plan["sections"]
    assert len(secs) >= 4
    assert secs[0]["start"] == 0.0
    for prev, nxt in zip(secs, secs[1:], strict=False):
        assert abs(prev["end"] - nxt["start"]) < 1e-6
        assert 0.0 <= nxt["energy"] <= 1.0
    assert plan["duration"] == round(secs[-1]["end"], 3)
    assert any(s["type"] == "chorus" for s in secs)


def test_scaffold_lyrics_land_in_lyric_sections():
    plan = songplan.plan_song(prompt="rivers of neon light", seed=11)
    assert plan["lyrics_source"] == "scaffold"
    lyric_types = {"verse", "pre_chorus", "chorus", "bridge", "breakdown"}
    for ln in plan["lyric_lines"]:
        assert plan["sections"][ln["section"]]["type"] in lyric_types
    assert len(plan["lyric_lines"]) >= len(
        [s for s in plan["sections"] if s["type"] in lyric_types]
    )


def test_provided_lyrics_are_used():
    plan = songplan.plan_song(
        prompt="x", seed=1, lyrics="line one\nline two\n\nchorus hook\nchorus hook two"
    )
    assert plan["lyrics_source"] == "provided"
    texts = [ln["text"] for ln in plan["lyric_lines"]]
    assert "line one" in texts and "chorus hook" in texts
