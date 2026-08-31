"""Stage 3 exit criteria: the same guide renders as each singer independently,
via a real voice provider, deterministically, consent-gated."""

from __future__ import annotations

import hashlib

import pytest


@pytest.fixture
def converted_section(client, guide_wav):
    singers = {}
    for name, prof in (
        ("Brian", {"median_f0": 110.0, "brightness": -0.5}),
        ("Pete", {"median_f0": 250.0, "brightness": 0.4, "breathiness": 0.3}),
    ):
        sid = client.post("/singers", json={"name": name}).json()["id"]
        client.patch(f"/singers/{sid}", json={"consent_generation": True})
        client.patch(f"/singers/{sid}/voice-model", json=prof)
        singers[name] = sid

    song = client.post("/songs", json={"title": "S3", "seed": 7}).json()["id"]
    section = client.post(
        f"/songs/{song}/sections",
        json={"section_type": "verse", "start_time": 0, "end_time": 3},
    ).json()["id"]
    client.post(
        f"/sections/{section}/roles",
        json={"role_type": "lead", "assignments": [{"singer_id": singers["Brian"]}]},
    )
    client.post(
        f"/sections/{section}/roles",
        json={
            "role_type": "harmony", "ensemble_size": 2,
            "assignments": [{"singer_id": singers["Pete"]}],
        },
    )
    with guide_wav.open("rb") as fh:
        assert client.post(
            f"/songs/{song}/sections/{section}/guide",
            files={"file": ("g.wav", fh, "audio/wav")},
        ).status_code == 201
    return song, section, singers


def _wav(client, song, asset_id):
    return client.get(f"/songs/{song}/assets/{asset_id}/download").content


def test_guide_is_converted_per_singer(client, converted_section):
    song, section, singers = converted_section
    job = client.post(f"/songs/{song}/sections/{section}/render", json={}).json()

    takes = client.get(f"/songs/{song}/renders/{job['id']}/takes").json()
    assert takes and all(t["source_kind"] == "converted" for t in takes)

    # each singer's take stem is a different rendering of the same guide
    stems = {
        a["singer_id"]: a["id"]
        for a in client.get(f"/songs/{song}/assets").json()
        if a["asset_type"] == "take_stem"
    }
    brian = _wav(client, song, stems[singers["Brian"]])
    pete = _wav(client, song, stems[singers["Pete"]])
    assert brian != pete and len(brian) > 1000


def test_conversion_render_is_deterministic_and_cached(client, converted_section):
    song, section, _ = converted_section

    def master_hash():
        job = client.post(
            f"/songs/{song}/sections/{section}/render", json={"seed": 7}
        ).json()
        master = next(
            a for a in client.get(f"/songs/{song}/assets").json()
            if a["asset_type"] == "master" and a["generation_job_id"] == job["id"]
        )
        return hashlib.sha256(_wav(client, song, master["id"])).hexdigest()

    assert master_hash() == master_hash()


def test_render_blocked_without_consent(client, guide_wav):
    sid = client.post("/singers", json={"name": "Nope"}).json()["id"]
    client.patch(f"/singers/{sid}/voice-model", json={"median_f0": 200.0})
    song = client.post("/songs", json={"title": "X"}).json()["id"]
    section = client.post(
        f"/songs/{song}/sections", json={"section_type": "verse"}
    ).json()["id"]
    client.post(
        f"/sections/{section}/roles",
        json={"role_type": "lead", "assignments": [{"singer_id": sid}]},
    )
    r = client.post(f"/songs/{song}/sections/{section}/render", json={})
    assert r.status_code == 403 and "Nope" in r.json()["detail"]


def test_no_guide_falls_back_to_placeholder(client):
    sid = client.post("/singers", json={"name": "Ghost"}).json()["id"]
    client.patch(f"/singers/{sid}", json={"consent_generation": True})
    client.patch(f"/singers/{sid}/voice-model", json={"median_f0": 200.0})
    song = client.post("/songs", json={"title": "X", "seed": 1}).json()["id"]
    section = client.post(
        f"/songs/{song}/sections", json={"section_type": "verse", "end_time": 2}
    ).json()["id"]
    client.post(
        f"/sections/{section}/roles",
        json={"role_type": "lead", "assignments": [{"singer_id": sid}]},
    )
    job = client.post(f"/songs/{song}/sections/{section}/render", json={}).json()
    takes = client.get(f"/songs/{song}/renders/{job['id']}/takes").json()
    assert all(t["source_kind"] == "mock" for t in takes)
