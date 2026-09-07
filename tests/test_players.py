"""Stage 12: the instrumentalist players roster (parallel to singers)."""

from __future__ import annotations


def test_create_list_and_filter_by_role(client):
    dave = client.post("/players", json={"name": "Dave", "role": "lead_guitar"})
    client.post("/players", json={"name": "Mike", "role": "rhythm_guitar"})
    client.post("/players", json={"name": "John", "role": "drums"})
    assert dave.status_code == 201
    assert dave.json()["role"] == "lead_guitar"
    assert dave.json()["training_status"] == "none"

    names = [p["name"] for p in client.get("/players").json()]
    assert set(names) == {"Dave", "Mike", "John"}

    guitars = client.get("/players", params={"role": "rhythm_guitar"}).json()
    assert [p["name"] for p in guitars] == ["Mike"]


def test_rejects_bad_role(client):
    r = client.post("/players", json={"name": "Nobody", "role": "triangle"})
    assert r.status_code == 422


def test_duplicate_name_within_band_rejected(client):
    assert client.post("/players", json={"name": "Dee", "role": "bass"}).status_code == 201
    assert client.post("/players", json={"name": "Dee", "role": "keys"}).status_code == 409


def test_players_scoped_per_band(client):
    b2 = client.post("/bands", json={"name": "Other"}).json()
    client.post("/players", json={"name": "Dee", "role": "bass"})
    client.post("/players", json={"name": "Dee", "role": "bass"}, headers={"X-Band-Id": b2["id"]})
    assert [p["name"] for p in client.get("/players").json()] == ["Dee"]
    assert len(client.get("/players", params={"band_id": b2["id"]}).json()) == 1


def test_update_and_delete(client):
    p = client.post("/players", json={"name": "Ed", "role": "lead_guitar"}).json()
    upd = client.patch(f"/players/{p['id']}", json={"display_name": "Fast Eddie", "intensity": 0.8})
    assert upd.status_code == 200
    assert upd.json()["display_name"] == "Fast Eddie"
    assert upd.json()["intensity"] == 0.8

    assert client.patch(f"/players/{p['id']}", json={"intensity": 2.0}).status_code == 422

    assert client.delete(f"/players/{p['id']}").status_code == 204
    assert client.get(f"/players/{p['id']}").status_code == 404


def test_deleting_band_cascades_players(client):
    b2 = client.post("/bands", json={"name": "Temp"}).json()
    client.post("/players", json={"name": "X", "role": "drums"}, headers={"X-Band-Id": b2["id"]})
    assert client.delete(f"/bands/{b2['id']}").status_code == 204
