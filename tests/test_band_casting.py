"""Stage 18: band lineup + one-click 'cast the whole band'."""

from __future__ import annotations


def _player(client, name, role, *, samples=0, consent=True):
    pid = client.post("/players", json={"name": name, "role": role}).json()["id"]
    if consent:
        client.patch(f"/players/{pid}", json={"consent_generation": True})
    if samples:
        client.patch(f"/players/{pid}/style-model", json={"drive": 0.5})
        # fake "trained" state by bumping training via manual profile is enough for pick order
    return pid


def test_band_lineup_summary(client):
    client.post("/players", json={"name": "Tony", "role": "rhythm_guitar"})
    client.post("/players", json={"name": "Geezer", "role": "bass"})
    client.post("/singers", json={"name": "Ozzy"})
    band_id = client.get("/bands").json()[0]["id"]
    lineup = client.get(f"/bands/{band_id}/lineup").json()
    assert [s["name"] for s in lineup["singers"]] == ["Ozzy"]
    assert [p["name"] for p in lineup["players"]["bass"]] == ["Geezer"]
    assert lineup["roles_filled"]["drums"] is False
    assert lineup["roles_filled"]["bass"] is False  # no consent yet


def test_cast_band_fills_instruments_and_vocals(client):
    _player(client, "Tony", "rhythm_guitar")
    _player(client, "Geezer", "bass")
    _player(client, "Bill", "drums")
    sid_singer = client.post("/singers", json={"name": "Ozzy"}).json()["id"]
    client.patch(f"/singers/{sid_singer}", json={"consent_generation": True})

    song = client.post("/songs", json={"title": "Paranoid", "seed": 7}).json()
    job = client.post(f"/songs/{song['id']}/generate", json={}).json()
    client.post(f"/jobs/{job['id']}/wait", params={"timeout": 120})

    r = client.post(f"/songs/{song['id']}/cast-band", json={"overwrite": True})
    assert r.status_code == 200
    body = r.json()
    assert body["players"]["bass"] == "Geezer"
    assert body["players"]["drums"] == "Bill"
    assert body["vocals"] is not None  # arranger ran

    slots = client.get(f"/songs/{song['id']}/instruments").json()
    by_role = {s["role"]: s["player_id"] for s in slots}
    assert by_role["rhythm_guitar"] and by_role["bass"] and by_role["drums"]


def test_cast_band_skips_roles_with_no_consenting_player(client):
    _player(client, "Solo", "lead_guitar", consent=False)
    song = client.post("/songs", json={"title": "x", "seed": 1}).json()
    r = client.post(f"/songs/{song['id']}/cast-band", json={}).json()
    assert "lead_guitar" not in r["players"]


def test_cast_band_prefers_the_more_trained_player(client):
    a = client.post("/players", json={"name": "Rookie", "role": "drums"}).json()["id"]
    b = client.post("/players", json={"name": "Pro", "role": "drums"}).json()["id"]
    for pid in (a, b):
        client.patch(f"/players/{pid}", json={"consent_generation": True})
    # give "Pro" a ready style so it sorts first
    client.patch(f"/players/{b}/style-model", json={"busyness": 0.7})
    song = client.post("/songs", json={"title": "x", "seed": 1}).json()
    r = client.post(f"/songs/{song['id']}/cast-band", json={}).json()
    assert r["players"]["drums"] == "Pro"
