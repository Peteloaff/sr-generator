"""Stage 4: vocal presets - save a stack recipe, drop it on any section."""

from __future__ import annotations


def _band_section(client, name_suffix=""):
    singers = {
        n: client.post("/singers", json={"name": n + name_suffix}).json()["id"]
        for n in ("Brian", "Pete")
    }
    song = client.post("/songs", json={"title": "P" + name_suffix}).json()["id"]
    section = client.post(
        f"/songs/{song}/sections", json={"section_type": "chorus"}
    ).json()["id"]
    return song, section, singers


def test_capture_and_apply_roundtrip(client):
    song, section, singers = _band_section(client)
    client.post(
        f"/sections/{section}/roles",
        json={
            "role_type": "background", "ensemble_size": 8, "width": 80,
            "humanize_timing_ms": 15,
            "processing": [{"type": "compressor", "ratio": 2.5}],
            "assignments": [
                {"singer_id": singers["Brian"], "weight_percent": 70, "interval_semitones": 0},
                {"singer_id": singers["Pete"], "weight_percent": 30, "interval_semitones": 3},
            ],
        },
    )

    preset = client.post(
        "/vocal-presets", json={"name": "Big Chorus", "from_section_id": section}
    ).json()
    assert preset["spec_json"]["roles"][0]["ensemble_size"] == 8

    section_b = client.post(
        f"/songs/{song}/sections", json={"section_type": "bridge"}
    ).json()["id"]
    res = client.post(f"/vocal-presets/{preset['id']}/apply", json={"section_id": section_b})
    assert res.status_code == 201
    body = res.json()
    assert len(body["created_roles"]) == 1
    assert body["skipped_singers"] == []
    role = body["created_roles"][0]
    assert role["ensemble_size"] == 8
    assert {a["interval_semitones"] for a in role["assignments"]} == {0.0, 3.0}


def test_unknown_singers_are_skipped_not_fatal(client):
    song, section, singers = _band_section(client)
    client.post(
        f"/sections/{section}/roles",
        json={"role_type": "gang", "assignments": [{"singer_id": singers["Brian"]}]},
    )
    preset = client.post(
        "/vocal-presets",
        json={
            "name": "Has Ghost",
            "spec": {
                "roles": [
                    {
                        "role_type": "gang", "ensemble_size": 4,
                        "assignments": [
                            {"singer": "Brian", "weight_percent": 50},
                            {"singer": "Nonexistent", "weight_percent": 50},
                        ],
                    }
                ]
            },
        },
    ).json()
    res = client.post(
        f"/vocal-presets/{preset['id']}/apply", json={"section_id": section}
    ).json()
    assert res["skipped_singers"] == ["Nonexistent"]
    assert len(res["created_roles"]) == 1


def test_preset_name_unique_per_band(client):
    _band_section(client)
    body = {"name": "X", "spec": {"roles": []}}
    assert client.post("/vocal-presets", json=body).status_code == 201
    assert client.post("/vocal-presets", json=body).status_code == 409
