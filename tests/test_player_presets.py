"""Stage 19: built-in signature style presets for instrument players."""

from __future__ import annotations

from sr.common import player_presets as pp
from sr.common.playerstyle import StyleProfile


def test_grid_covers_every_role_and_vibe():
    presets = pp.list_presets()
    assert len(presets) == 5 * len(pp.VIBES) + len(pp.SIGNATURES)  # no vocals
    ids = {p["id"] for p in presets}
    assert "lead_guitar.acoustic" in ids
    assert "drums.modern_metal" in ids
    assert "bass.doom" in ids


def test_signature_presets():
    presets = {p["id"]: p for p in pp.list_presets()}
    assert presets["rhythm_guitar.timmy"]["role"] == "rhythm_guitar"
    assert presets["lead_guitar.ted"]["role"] == "lead_guitar"
    assert presets["drums.bonzo"]["role"] == "drums"
    assert presets["bass.will"]["role"] == "bass"
    assert presets["lead_guitar.street"]["role"] == "lead_guitar"
    assert presets["rhythm_guitar.book"]["role"] == "rhythm_guitar"
    assert presets["drums.bruce"]["role"] == "drums"
    assert presets["drums.numbers"]["role"] == "drums"
    assert presets["drums.kansas"]["role"] == "drums"
    assert presets["bass.bug"]["role"] == "bass"
    assert presets["bass.swim"]["role"] == "bass"
    for codename, role in pp.SIGNATURES.items():
        sp = StyleProfile.from_dict(pp.get_preset(f"{role}.{codename}")["profile"])
        assert 0.0 <= sp.drive <= 1.0
        assert -1.0 <= sp.brightness <= 1.0


def test_profiles_are_valid_and_directional():
    acoustic = pp.get_preset("rhythm_guitar.acoustic")["profile"]
    metal = pp.get_preset("rhythm_guitar.metal")["profile"]
    doom = pp.get_preset("rhythm_guitar.doom")["profile"]
    assert acoustic["drive"] < 0.1 < metal["drive"]
    assert metal["drive"] >= 0.9
    assert doom["brightness"] < acoustic["brightness"]
    assert doom["sustain"] > metal["sustain"]
    for p in pp.list_presets():
        sp = StyleProfile.from_dict(p["profile"])
        assert 0.0 <= sp.drive <= 1.0
        assert -1.0 <= sp.brightness <= 1.0


def test_unknown_preset_is_none():
    assert pp.get_preset("guitar.zappa") is None
    assert pp.get_preset("nonsense") is None


def test_api_lists_and_filters_presets(client):
    allp = client.get("/players/presets").json()
    assert len(allp) == 5 * len(pp.VIBES) + len(pp.SIGNATURES)
    drums = client.get("/players/presets", params={"role": "drums"}).json()
    assert {d["role"] for d in drums} == {"drums"}
    assert any(d["vibe"] == "modern_metal" for d in drums)


def test_create_player_from_preset(client):
    r = client.post(
        "/players/from-preset",
        json={"preset": "drums.modern_metal", "name": "Modern Metal Drums"},
    )
    assert r.status_code == 201
    p = r.json()
    assert p["role"] == "drums"
    assert p["training_status"] == "ready"
    assert p["consent_generation"] is True
    assert p["style_model_provider"] == "preset"
    assert p["style_profile_json"]["busyness"] > 0.9

    dup = client.post(
        "/players/from-preset",
        json={"preset": "drums.modern_metal", "name": "Modern Metal Drums"},
    )
    assert dup.status_code == 409


def test_apply_preset_to_existing_player(client):
    pid = client.post("/players", json={"name": "Ed", "role": "lead_guitar"}).json()["id"]
    r = client.post(f"/players/{pid}/apply-preset", json={"preset": "lead_guitar.doom"})
    assert r.status_code == 200
    assert r.json()["style_profile_json"]["brightness"] < 0

    wrong = client.post(f"/players/{pid}/apply-preset", json={"preset": "drums.metal"})
    assert wrong.status_code == 422
