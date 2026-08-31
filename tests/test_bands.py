"""Band scoping: a second band is fully isolated - the "use it for another band" hedge."""

from __future__ import annotations


def test_default_band_autocreated(client):
    bands = client.get("/bands").json()
    assert len(bands) == 1
    assert bands[0]["slug"] == "default"


def test_singers_are_scoped_per_band(client):
    b2 = client.post("/bands", json={"name": "Second Band"}).json()

    # same name in each band is fine
    s1 = client.post("/singers", json={"name": "Chris"})
    s2 = client.post("/singers", json={"name": "Chris"}, headers={"X-Band-Id": b2["id"]})
    assert s1.status_code == 201 and s2.status_code == 201
    assert s1.json()["band_id"] != s2.json()["band_id"]

    # duplicate within one band is rejected
    assert client.post("/singers", json={"name": "Chris"}).status_code == 409

    # lists are filtered by band
    assert [s["name"] for s in client.get("/singers").json()] == ["Chris"]
    assert len(client.get("/singers", params={"band_id": b2["id"]}).json()) == 1

    stats = client.get(f"/bands/{b2['id']}/stats").json()
    assert stats["singers"] == 1


def test_deleting_band_cascades(client):
    b2 = client.post("/bands", json={"name": "Temp"}).json()
    client.post("/singers", json={"name": "X"}, headers={"X-Band-Id": b2["id"]})
    client.post("/projects", json={"name": "P"}, headers={"X-Band-Id": b2["id"]})
    assert client.delete(f"/bands/{b2['id']}").status_code == 204
    assert client.get(f"/bands/{b2['id']}").status_code == 404


def test_default_band_cannot_be_deleted(client):
    default_id = client.get("/bands").json()[0]["id"]
    assert client.delete(f"/bands/{default_id}").status_code == 409
