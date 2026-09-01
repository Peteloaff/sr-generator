"""Stage 8 exit criteria: a prompt becomes a complete, editable song project -
independently editable sections + singer assignments, stems, and a master; never
a single opaque file.
"""

from __future__ import annotations

import hashlib

import pytest


@pytest.fixture
def band_with_singers(client):
    band = client.get("/bands").json()[0]["id"]
    ids = {}
    for name, f0 in (("Brian", 120.0), ("Pete", 180.0)):
        sid = client.post("/singers", json={"name": name}).json()["id"]
        client.patch(f"/singers/{sid}", json={"consent_generation": True})
        client.patch(f"/singers/{sid}/voice-model", json={"median_f0": f0})
        ids[name] = sid
    return band, ids


def _generate(client, song_id, **body):
    job = client.post(f"/songs/{song_id}/generate", json=body).json()
    return client.post(f"/jobs/{job['id']}/wait", params={"timeout": 120}).json()


def test_prompt_becomes_a_full_editable_project(client, band_with_singers):
    song = client.post("/songs", json={"title": "Gen One"}).json()["id"]
    job = _generate(client, song, prompt="a driving night-time anthem", seed=21)
    assert job["status"] == "succeeded", job.get("error")

    sections = client.get(f"/songs/{song}/sections").json()
    assert len(sections) >= 5
    # every verse / chorus has at least one role with a singer
    for s in sections:
        if s["section_type"] in ("verse", "chorus"):
            roles = client.get(f"/sections/{s['id']}/roles").json()
            assert any(r["assignments"] for r in roles), s

    lines = client.get(f"/songs/{song}/lines").json()
    assert len(lines) >= 4

    assets = client.get(f"/songs/{song}/assets").json()
    kinds = {a["asset_type"] for a in assets}
    # not one opaque file: sections, stems, and a song master all exist separately
    assert {"song_mix", "song_master", "stem_instrumental", "vocal_bus"} <= kinds
    assert {"instrumental_bed", "guide_vocal", "mix", "master", "take_stem"} <= kinds
    assert len(assets) > 15

    meta = job["result_json"]
    assert meta["sections_created"] == len(sections)
    assert meta["sections_rendered"] >= 2


def test_a_single_section_regenerates_without_touching_the_rest(client, band_with_singers):
    song = client.post("/songs", json={"title": "Gen Two"}).json()["id"]
    _generate(client, song, prompt="slow burning ballad", seed=5)

    sections = client.get(f"/songs/{song}/sections").json()
    target = next(s for s in sections if s["section_type"] == "chorus")
    other = next(s for s in sections if s["id"] != target["id"]
                 and client.get(f"/sections/{s['id']}/roles").json())

    def masters(section_id):
        return {
            a["id"]: a
            for a in client.get(f"/songs/{song}/assets").json()
            if a["section_id"] == section_id and a["asset_type"] == "master"
        }

    def sha(asset_id):
        return hashlib.sha256(
            client.get(f"/songs/{song}/assets/{asset_id}/download").content
        ).hexdigest()

    other_master = next(iter(masters(other["id"])))
    target_masters_before = set(masters(target["id"]))
    before_other = sha(other_master)
    before_target = sha(next(iter(target_masters_before)))

    job = client.post(
        f"/songs/{song}/sections/{target['id']}/render", json={"seed": 999}
    ).json()
    client.post(f"/jobs/{job['id']}/wait", params={"timeout": 90})

    new_target_master = (set(masters(target["id"])) - target_masters_before).pop()
    assert sha(other_master) == before_other  # untouched section byte-identical
    assert sha(new_target_master) != before_target  # target section changed


def test_generation_is_reproducible_from_a_seed(client, band_with_singers):
    s1 = client.post("/songs", json={"title": "R1"}).json()["id"]
    s2 = client.post("/songs", json={"title": "R2"}).json()["id"]
    j1 = _generate(client, s1, prompt="same prompt here", seed=77)
    j2 = _generate(client, s2, prompt="same prompt here", seed=77)

    def song_master(song_id, job):
        aid = job["result_json"]["song_master_asset_id"]
        return hashlib.sha256(
            client.get(f"/songs/{song_id}/assets/{aid}/download").content
        ).hexdigest()

    types1 = [s["section_type"] for s in client.get(f"/songs/{s1}/sections").json()]
    types2 = [s["section_type"] for s in client.get(f"/songs/{s2}/sections").json()]
    assert types1 == types2
    assert song_master(s1, j1) == song_master(s2, j2)
