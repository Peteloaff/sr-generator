"""Stage 15: instrument casting - assign players per section, conditioned render."""

from __future__ import annotations


def _player(client, name, role, *, profile=None, consent=True):
    pid = client.post("/players", json={"name": name, "role": role}).json()["id"]
    if consent:
        client.patch(f"/players/{pid}", json={"consent_generation": True})
    if profile:
        client.patch(f"/players/{pid}/style-model", json=profile)
    return pid


def _song_with_sections(client, **extra):
    song = client.post("/songs", json={"title": "Cast Test", "seed": 5, **extra}).json()
    job = client.post(f"/songs/{song['id']}/generate", json={}).json()
    client.post(f"/jobs/{job['id']}/wait", params={"timeout": 120})
    secs = client.get(f"/songs/{song['id']}/sections").json()
    return song, secs


def test_set_and_list_instrument_slots(client):
    song, _ = _song_with_sections(client)
    drummer = _player(client, "John", "drums")
    r = client.put(
        f"/songs/{song['id']}/instruments",
        json={"role": "drums", "player_id": drummer},
    )
    assert r.status_code == 200
    slots = client.get(f"/songs/{song['id']}/instruments").json()
    assert len(slots) == 1
    assert slots[0]["role"] == "drums" and slots[0]["player_id"] == drummer
    assert slots[0]["section_id"] is None  # whole-song default


def test_wrong_role_player_rejected(client):
    song, _ = _song_with_sections(client)
    bassist = _player(client, "Dee", "bass")
    r = client.put(
        f"/songs/{song['id']}/instruments",
        json={"role": "drums", "player_id": bassist},
    )
    assert r.status_code == 422


def test_casting_reaches_the_render(client):
    song, secs = _song_with_sections(client)
    drummer = _player(
        client, "John Bonham", "drums",
        profile={"busyness": 0.85, "swing": 0.3, "dynamics": 0.8},
    )
    client.put(
        f"/songs/{song['id']}/instruments",
        json={"role": "drums", "player_id": drummer},
    )
    sid = secs[0]["id"]
    job = client.post(
        f"/songs/{song['id']}/sections/{sid}/generate-instrumental", json={}
    ).json()
    done = client.post(f"/jobs/{job['id']}/wait", params={"timeout": 120}).json()
    assert done["status"] == "succeeded", done.get("error")
    assert done["result_json"]["cast"] == {"drums": "John Bonham"}

    assets = client.get(f"/songs/{song['id']}/assets").json()
    types = {a["asset_type"] for a in assets if a["section_id"] == sid}
    assert "stem_drums" in types and "stem_bass" in types


def test_mute_silences_a_part(client):
    song, secs = _song_with_sections(client)
    client.put(
        f"/songs/{song['id']}/instruments",
        json={"role": "lead_guitar", "player_id": None, "muted": True},
    )
    sid = secs[0]["id"]
    job = client.post(
        f"/songs/{song['id']}/sections/{sid}/generate-instrumental", json={}
    ).json()
    client.post(f"/jobs/{job['id']}/wait", params={"timeout": 120})
    assets = client.get(f"/songs/{song['id']}/assets").json()
    lead = [a for a in assets if a["asset_type"] == "stem_lead" and a["section_id"] == sid]
    # a fully-muted part is not written as an asset at all
    assert lead == []


def test_section_override_beats_song_default(client):
    song, secs = _song_with_sections(client)
    a = _player(client, "Default Drummer", "drums")
    b = _player(client, "Chorus Drummer", "drums")
    client.put(f"/songs/{song['id']}/instruments", json={"role": "drums", "player_id": a})
    client.put(
        f"/songs/{song['id']}/instruments",
        json={"role": "drums", "player_id": b, "section_id": secs[1]["id"]},
    )
    j0 = client.post(
        f"/songs/{song['id']}/sections/{secs[0]['id']}/generate-instrumental", json={}
    ).json()
    j1 = client.post(
        f"/songs/{song['id']}/sections/{secs[1]['id']}/generate-instrumental", json={}
    ).json()
    d0 = client.post(f"/jobs/{j0['id']}/wait", params={"timeout": 120}).json()
    d1 = client.post(f"/jobs/{j1['id']}/wait", params={"timeout": 120}).json()
    assert d0["result_json"]["cast"]["drums"] == "Default Drummer"
    assert d1["result_json"]["cast"]["drums"] == "Chorus Drummer"


def test_unconsented_player_is_ignored(client):
    song, secs = _song_with_sections(client)
    pid = _player(client, "No Consent", "bass", consent=False)
    client.put(f"/songs/{song['id']}/instruments", json={"role": "bass", "player_id": pid})
    job = client.post(
        f"/songs/{song['id']}/sections/{secs[0]['id']}/generate-instrumental", json={}
    ).json()
    done = client.post(f"/jobs/{job['id']}/wait", params={"timeout": 120}).json()
    assert done["result_json"].get("cast", {}) == {}
