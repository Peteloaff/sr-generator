"""Stage 10 exit criteria: the arranger recommends a complete, editable vocal map
for every section and never overwrites existing assignments without an explicit
action.
"""

from __future__ import annotations

import pytest


@pytest.fixture
def song_and_singers(client):
    client.get("/bands").json()
    brian = client.post("/singers", json={"name": "Brian"}).json()["id"]
    pete = client.post("/singers", json={"name": "Pete"}).json()["id"]
    client.patch(f"/singers/{brian}", json={
        "consent_generation": True,
        "preferred_roles": ["chorus_lead", "scream", "high_harmony", "gang"],
        "energy_fit": "high", "scream_enabled": True,
        "range_low_midi": 48, "range_high_midi": 72,
    })
    client.patch(f"/singers/{pete}", json={
        "consent_generation": True,
        "preferred_roles": ["verse_lead", "octave_double", "low_harmony"],
        "energy_fit": "mid",
        "range_low_midi": 45, "range_high_midi": 64,
    })

    song = client.post("/songs", json={"title": "S10", "seed": 9, "bpm": 128}).json()["id"]
    secs = {}
    for stype, a, b in (("verse", 0, 8), ("chorus", 8, 16), ("breakdown", 16, 24)):
        secs[stype] = client.post(
            f"/songs/{song}/sections",
            json={"section_type": stype, "start_time": a, "end_time": b},
        ).json()["id"]
    client.put(
        f"/songs/{song}/lines",
        json={"text": "one two three four\nfive six seven eight", "section_id": secs["verse"]},
    )
    return song, secs, {"Brian": brian, "Pete": pete}


def test_recommendation_is_complete_and_scored(client, song_and_singers):
    song, secs, ids = song_and_singers
    rec = client.get(f"/songs/{song}/arrangement/recommend").json()
    assert len(rec["sections"]) == 3
    for s in rec["sections"]:
        assert s["recommendations"], s
        leads = [r for r in s["recommendations"] if r["role_type"] == "lead"]
        assert len(leads) == 1
        for r in s["recommendations"]:
            assert 0.0 <= r["confidence"] <= 1.0
            assert r["rationale"]

    by_type = {s["section_type"]: s for s in rec["sections"]}
    chorus_lead = next(
        r for r in by_type["chorus"]["recommendations"] if r["role_type"] == "lead"
    )
    assert chorus_lead["assignments"][0]["singer_id"] == ids["Brian"]  # prefers chorus_lead
    verse_lead = next(
        r for r in by_type["verse"]["recommendations"] if r["role_type"] == "lead"
    )
    assert verse_lead["assignments"][0]["singer_id"] == ids["Pete"]  # prefers verse_lead
    assert any(r["role_type"] == "gang" for r in by_type["breakdown"]["recommendations"])


def test_apply_creates_editable_roles_and_never_clobbers(client, song_and_singers):
    song, secs, ids = song_and_singers

    res = client.post(f"/songs/{song}/arrangement/apply", json={}).json()
    assert {a["section_id"] for a in res["applied"]} == set(secs.values())
    assert res["skipped"] == []

    chorus_roles = client.get(f"/sections/{secs['chorus']}/roles").json()
    assert any(r["role_type"] == "lead" for r in chorus_roles)
    # editable: a plain PATCH on a recommended role works
    role = chorus_roles[0]
    client.patch(f"/roles/{role['id']}", json={"width": 33})
    assert client.get(f"/roles/{role['id']}").json()["width"] == 33

    # re-apply without overwrite: every section is skipped, nothing changes
    n_before = {s: len(client.get(f"/sections/{s}/roles").json()) for s in secs.values()}
    res2 = client.post(f"/songs/{song}/arrangement/apply", json={}).json()
    assert res2["applied"] == []
    assert {s["reason"] for s in res2["skipped"]} == {"already has roles"}
    n_after = {s: len(client.get(f"/sections/{s}/roles").json()) for s in secs.values()}
    assert n_after == n_before

    # explicit overwrite replaces them
    res3 = client.post(
        f"/songs/{song}/arrangement/apply", json={"overwrite": True}
    ).json()
    assert len(res3["applied"]) == 3 and res3["skipped"] == []


def test_locked_section_is_skipped(client, song_and_singers):
    song, secs, _ = song_and_singers
    client.post(f"/sections/{secs['verse']}/lock", params={"locked": True})
    res = client.post(f"/songs/{song}/arrangement/apply", json={}).json()
    skipped = {s["section_id"]: s["reason"] for s in res["skipped"]}
    assert skipped.get(secs["verse"]) == "locked"
    assert client.get(f"/sections/{secs['verse']}/roles").json() == []
