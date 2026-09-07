"""Stage 14: genre / song-feel presets shape the whole song."""

from __future__ import annotations

import numpy as np

from sr.common import genre, musicgen
from sr.services import songplan
from sr.services.music import blend_character


def test_genre_list_and_lookup(client):
    genres = client.get("/genres").json()
    ids = {g["id"] for g in genres}
    assert {"metal", "sludge_metal", "acoustic", "pop"} <= ids

    sludge = client.get("/genres/sludge_metal").json()
    assert sludge["tuning_semitones"] == -3
    assert sludge["character"]["distortion"] == 1.0
    assert client.get("/genres/nonsense").status_code == 404


def test_plan_bias_changes_tempo_and_section_length():
    fast = songplan.plan_song(prompt="x", seed=1, genre="thrash_metal")
    slow = songplan.plan_song(prompt="x", seed=1, genre="doom_metal")
    assert fast["bpm"] > 160
    assert slow["bpm"] < 80
    # doom sections run much longer than thrash sections
    assert slow["sections"][0]["seconds"] > fast["sections"][0]["seconds"] * 1.5
    assert slow["genre"] == "doom_metal"


def test_minor_genre_biases_key_to_minor():
    plan = songplan.plan_song(prompt="x", seed=3, genre="black_metal")
    assert "minor" in plan["key"]


def test_character_is_audibly_different():
    def energy(gname):
        ch = genre.character(gname)
        a = musicgen.generate(bpm=120, key="A minor", seconds=3.0, seed=5, character=ch)["audio"]
        return float(np.sqrt(np.mean(a**2)))

    # distorted/dense genres sit hotter at the same peak than clean ones
    assert energy("sludge_metal") > energy("acoustic") * 1.4


def test_blend_character_interpolates():
    band = {"brightness": 1.0, "drive": 0.0, "drum_busy": 0.5}
    pure_band = blend_character("metal", band, 0.0)
    pure_genre = blend_character("metal", band, 1.0)
    half = blend_character("metal", band, 0.5)
    assert pure_band["brightness"] == 1.0
    assert pure_genre["drive"] > 0.8
    assert pure_band["brightness"] > half["brightness"] > pure_genre["brightness"]


def test_song_generation_uses_genre(client):
    song = client.post(
        "/songs", json={"title": "Doom Test", "genre": "doom_metal", "seed": 11}
    ).json()
    assert song["genre"] == "doom_metal"
    assert song["style_blend"] == 0.6

    jr = client.post(f"/songs/{song['id']}/generate", json={})
    assert jr.status_code == 201, jr.text
    job = jr.json()
    wr = client.post(f"/jobs/{job['id']}/wait", params={"timeout": 120})
    assert wr.status_code == 200, wr.text
    done = wr.json()
    assert done["status"] == "succeeded", done.get("error")
    got = client.get(f"/songs/{song['id']}").json()
    assert got["genre"] == "doom_metal"
    assert got["bpm"] < 80  # doom tempo range
