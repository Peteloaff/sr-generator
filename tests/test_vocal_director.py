"""Stage 1: Vocal Director - roles, weighted assignments, normalization."""

from __future__ import annotations

import pytest


@pytest.fixture
def song_with_chorus(client):
    song_id = client.post("/songs", json={"title": "S"}).json()["id"]
    sec_id = client.post(
        f"/songs/{song_id}/sections", json={"section_type": "chorus"}
    ).json()["id"]
    singers = {
        n: client.post("/singers", json={"name": n}).json()["id"]
        for n in ("Brian", "Pete", "Brad")
    }
    return song_id, sec_id, singers


def test_background_role_normalizes_and_allocates(client, song_with_chorus):
    _, sec_id, s = song_with_chorus
    role = client.post(
        f"/sections/{sec_id}/roles",
        json={
            "role_type": "background",
            "ensemble_size": 10,
            "assignments": [
                {"singer_id": s["Brian"], "weight_percent": 70},
                {"singer_id": s["Pete"], "weight_percent": 20},
                {"singer_id": s["Brad"], "weight_percent": 10},
            ],
        },
    ).json()

    shares = client.get(f"/roles/{role['id']}/normalized").json()
    by_singer = {x["singer_id"]: x for x in shares}
    assert by_singer[s["Brian"]]["ensemble_takes"] == 7
    assert by_singer[s["Pete"]]["ensemble_takes"] == 2
    assert by_singer[s["Brad"]]["ensemble_takes"] == 1
    assert sum(x["normalized_percent"] for x in shares) == pytest.approx(100.0)


def test_weights_need_not_sum_to_100(client, song_with_chorus):
    _, sec_id, s = song_with_chorus
    role = client.post(
        f"/sections/{sec_id}/roles",
        json={
            "role_type": "background",
            "ensemble_size": 8,
            "assignments": [
                {"singer_id": s["Brian"], "weight_percent": 3},
                {"singer_id": s["Pete"], "weight_percent": 1},
            ],
        },
    ).json()
    shares = {x["singer_id"]: x for x in client.get(f"/roles/{role['id']}/normalized").json()}
    assert shares[s["Brian"]]["normalized_percent"] == pytest.approx(75.0)
    assert shares[s["Brian"]]["ensemble_takes"] + shares[s["Pete"]]["ensemble_takes"] == 8


def test_lead_role_is_single_take(client, song_with_chorus):
    _, sec_id, s = song_with_chorus
    role = client.post(
        f"/sections/{sec_id}/roles",
        json={
            "role_type": "lead",
            "assignments": [{"singer_id": s["Brian"], "weight_percent": 100}],
        },
    ).json()
    shares = client.get(f"/roles/{role['id']}/normalized").json()
    assert shares[0]["ensemble_takes"] == 1


def test_assignment_crud_and_dup_guard(client, song_with_chorus):
    _, sec_id, s = song_with_chorus
    role = client.post(f"/sections/{sec_id}/roles", json={"role_type": "gang"}).json()
    a = client.post(
        f"/roles/{role['id']}/assignments", json={"singer_id": s["Pete"], "weight_percent": 50}
    )
    assert a.status_code == 201
    assert (
        client.post(f"/roles/{role['id']}/assignments", json={"singer_id": s["Pete"]}).status_code
        == 409
    )
    upd = client.patch(f"/assignments/{a.json()['id']}", json={"gain_db": -3.0, "pan": -25})
    assert upd.json()["gain_db"] == -3.0
    assert client.delete(f"/assignments/{a.json()['id']}").status_code == 204


def test_role_rejects_singer_from_other_band(client, song_with_chorus):
    _, sec_id, _s = song_with_chorus
    other = client.post("/bands", json={"name": "Other"}).json()["id"]
    foreign = client.post(
        "/singers", json={"name": "Outsider"}, headers={"X-Band-Id": other}
    ).json()["id"]
    r = client.post(
        f"/sections/{sec_id}/roles",
        json={"role_type": "lead", "assignments": [{"singer_id": foreign}]},
    )
    assert r.status_code == 422


def test_line_role_overrides_section_via_api(client, song_with_chorus):
    song_id, sec_id, s = song_with_chorus
    line_id = client.post(
        f"/songs/{song_id}/lines", json={"text": "hook", "section_id": sec_id}
    ).json()["id"]
    client.post(
        f"/sections/{sec_id}/roles",
        json={"role_type": "lead", "assignments": [{"singer_id": s["Brian"]}]},
    )
    client.post(
        f"/lines/{line_id}/roles",
        json={"role_type": "lead", "assignments": [{"singer_id": s["Pete"]}]},
    )
    resolved = client.get(f"/songs/{song_id}/lines/{line_id}/resolved-roles").json()
    assert resolved["source"] == "line"
    assert resolved["roles"][0]["assignments"][0]["singer_id"] == s["Pete"]
