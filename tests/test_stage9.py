"""Stage 9 exit criteria: change one section / role / singer without materially
altering the rest; locked sections are protected; edits roll back.
"""

from __future__ import annotations

import hashlib

import pytest


@pytest.fixture
def rendered_song(client):
    client.get("/bands").json()
    singers = {}
    for name in ("Brian", "Pete", "Brad"):
        sid = client.post("/singers", json={"name": name}).json()["id"]
        client.patch(f"/singers/{sid}", json={"consent_generation": True})
        client.patch(f"/singers/{sid}/voice-model", json={"median_f0": 130.0})
        singers[name] = sid

    song = client.post("/songs", json={"title": "S9", "seed": 4, "bpm": 120}).json()["id"]
    sections = []
    for stype in ("verse", "chorus"):
        sec = client.post(
            f"/songs/{song}/sections",
            json={"section_type": stype, "start_time": 0, "end_time": 4},
        ).json()["id"]
        client.post(
            f"/sections/{sec}/roles",
            json={"role_type": "lead", "assignments": [{"singer_id": singers["Brian"]}]},
        )
        client.post(
            f"/sections/{sec}/roles",
            json={
                "role_type": "gang", "ensemble_size": 6, "width": 70,
                "humanize_timing_ms": 20, "humanize_pitch_cents": 8,
                "assignments": [
                    {"singer_id": singers["Brian"], "weight_percent": 50},
                    {"singer_id": singers["Pete"], "weight_percent": 30},
                    {"singer_id": singers["Brad"], "weight_percent": 20},
                ],
            },
        )
        j = client.post(f"/songs/{song}/sections/{sec}/render", json={}).json()
        client.post(f"/jobs/{j['id']}/wait", params={"timeout": 90})
        sections.append(sec)
    return song, sections, singers


def _assets(client, song):
    return client.get(f"/songs/{song}/assets").json()


def _sha(client, song, asset_id):
    return hashlib.sha256(
        client.get(f"/songs/{song}/assets/{asset_id}/download").content
    ).hexdigest()


def _role_stem(client, song, section_id, prefix, exclude=()):
    for a in _assets(client, song):
        if (
            a["section_id"] == section_id
            and a["asset_type"] == "role_stem"
            and (a["label"] or "").startswith(prefix)
            and a["id"] not in exclude
        ):
            yield a["id"]


def test_regenerate_section_isolated(client, rendered_song):
    song, (verse, chorus), _ = rendered_song
    verse_master = next(
        a["id"] for a in _assets(client, song)
        if a["section_id"] == verse and a["asset_type"] == "master"
    )
    before = _sha(client, song, verse_master)

    job = client.post(
        f"/sections/{chorus}/regenerate", json={"seed": 555, "note": "brighter"}
    ).json()
    assert job["status"] == "succeeded", job.get("error")
    assert job["result_json"]["revision"] == 1

    assert _sha(client, song, verse_master) == before  # verse untouched

    revs = client.get(f"/sections/{chorus}/revisions").json()
    assert revs[0]["kind"] == "full" and revs[0]["is_current"]


def test_regenerate_one_role_preserves_the_others(client, rendered_song):
    song, (verse, _), _ = rendered_song
    lead_before = set(_role_stem(client, song, verse, "lead"))
    gang_before = set(_role_stem(client, song, verse, "gang"))
    lead_sha = _sha(client, song, next(iter(lead_before)))

    gang_role = next(
        r for r in client.get(f"/sections/{verse}/roles").json()
        if r["role_type"] == "gang"
    )
    job = client.post(
        f"/roles/{gang_role['id']}/regenerate", json={"seed": 4}
    ).json()
    assert job["status"] == "succeeded", job.get("error")

    lead_after = next(iter(_role_stem(client, song, verse, "lead", exclude=lead_before)))
    gang_after = next(iter(_role_stem(client, song, verse, "gang", exclude=gang_before)))
    assert _sha(client, song, lead_after) == lead_sha  # lead layer identical
    assert _sha(client, song, gang_after) != _sha(client, song, next(iter(gang_before)))


def test_swap_singer_only(client, rendered_song):
    song, (verse, _), singers = rendered_song
    lead_role = next(
        r for r in client.get(f"/sections/{verse}/roles").json()
        if r["role_type"] == "lead"
    )
    job = client.post(
        f"/roles/{lead_role['id']}/regenerate",
        json={"swap_from_singer_id": singers["Brian"], "swap_to_singer_id": singers["Pete"]},
    ).json()
    assert job["status"] == "succeeded", job.get("error")
    assert job["result_json"]["regen"] == "swap"

    roles = client.get(f"/sections/{verse}/roles").json()
    lead = next(r for r in roles if r["role_type"] == "lead")
    assert lead["assignments"][0]["singer_id"] == singers["Pete"]
    revs = client.get(f"/sections/{verse}/revisions").json()
    assert revs[0]["kind"] == "swap"


def test_locked_section_refuses_regeneration(client, rendered_song):
    song, (verse, chorus), _ = rendered_song
    client.post(f"/sections/{verse}/lock", params={"locked": True})
    r = client.post(f"/sections/{verse}/regenerate", json={})
    assert r.status_code == 423
    client.post(f"/sections/{verse}/lock", params={"locked": False})
    assert client.post(f"/sections/{verse}/regenerate", json={}).json()["status"] == "succeeded"


def test_rollback_restores_the_arrangement(client, rendered_song):
    song, (verse, _), singers = rendered_song
    client.post(f"/sections/{verse}/regenerate", json={})  # revision 1

    before = client.get(f"/sections/{verse}/roles").json()
    n_before = len(before)
    client.post(
        f"/sections/{verse}/roles",
        json={"role_type": "double", "assignments": [{"singer_id": singers["Pete"]}]},
    )
    client.post(f"/sections/{verse}/regenerate", json={})  # revision 2, now with the double
    assert len(client.get(f"/sections/{verse}/roles").json()) == n_before + 1

    restored = client.post(
        f"/sections/{verse}/rollback", json={"revision": 1}
    ).json()
    assert len(restored) == n_before
    assert {r["role_type"] for r in restored} == {r["role_type"] for r in before}
