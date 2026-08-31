"""Stage 2 exit criteria: render a chorus with weighted gang allocation into
isolated + combined stems, repeatably from a seed."""

from __future__ import annotations

import hashlib

import pytest


@pytest.fixture
def chorus(client):
    singers = {
        n: client.post("/singers", json={"name": n}).json()["id"]
        for n in ("Brian", "Pete", "Brad")
    }
    song = client.post("/songs", json={"title": "Render", "seed": 99}).json()["id"]
    section = client.post(
        f"/songs/{song}/sections",
        json={"section_type": "chorus", "start_time": 0, "end_time": 3},
    ).json()["id"]
    client.post(
        f"/sections/{section}/roles",
        json={"role_type": "lead", "assignments": [{"singer_id": singers["Brian"]}]},
    )
    client.post(
        f"/sections/{section}/roles",
        json={
            "role_type": "gang",
            "ensemble_size": 10,
            "width": 85,
            "humanize_timing_ms": 18,
            "humanize_pitch_cents": 6,
            "assignments": [
                {"singer_id": singers["Brian"], "weight_percent": 70},
                {"singer_id": singers["Pete"], "weight_percent": 20},
                {"singer_id": singers["Brad"], "weight_percent": 10},
            ],
        },
    )
    return song, section, singers


def _download(client, song, asset_id) -> bytes:
    r = client.get(f"/songs/{song}/assets/{asset_id}/download")
    assert r.status_code == 200
    return r.content


def test_render_produces_isolated_and_combined_stems(client, chorus):
    song, section, _ = chorus
    job = client.post(f"/songs/{song}/sections/{section}/render", json={}).json()
    assert job["status"] == "succeeded"
    assert job["provider"] == "layering-engine"

    kinds = {a["asset_type"] for a in client.get(f"/songs/{song}/assets").json()}
    assert {"take_stem", "role_stem", "stem_lead_vocal", "stem_gang_vocal",
            "vocal_bus", "mix", "master"} <= kinds

    # 11 takes: lead(1) + gang(7/2/1)
    takes = client.get(f"/songs/{song}/renders/{job['id']}/takes").json()
    assert len(takes) == 11
    gang = [t for t in takes if t["pan"] != 0.0 or t["timing_offset_ms"] != 0.0]
    assert len({round(t["timing_offset_ms"], 3) for t in gang}) > 1  # takes really differ

    master = next(a for a in client.get(f"/songs/{song}/assets").json()
                  if a["asset_type"] == "master")
    wav = _download(client, song, master["id"])
    assert wav[:4] == b"RIFF" and len(wav) > 1000


def test_render_is_repeatable_from_a_seed(client, chorus):
    song, section, _ = chorus

    def render_and_hash(seed):
        job = client.post(
            f"/songs/{song}/sections/{section}/render", json={"seed": seed}
        ).json()
        master = next(
            a for a in client.get(f"/songs/{song}/assets").json()
            if a["asset_type"] == "master" and a["generation_job_id"] == job["id"]
        )
        return hashlib.sha256(_download(client, song, master["id"])).hexdigest()

    assert render_and_hash(99) == render_and_hash(99)
    assert render_and_hash(99) != render_and_hash(1234)


def test_uploaded_source_take_is_used(client, chorus, sample_wav):
    song, section, singers = chorus
    with sample_wav.open("rb") as fh:
        r = client.post(
            f"/songs/{song}/sections/{section}/takes",
            data={"singer_id": singers["Brian"]},
            files={"file": ("brian.wav", fh, "audio/wav")},
        )
    assert r.status_code == 201 and r.json()["asset_type"] == "source_take"

    job = client.post(f"/songs/{song}/sections/{section}/render", json={}).json()
    takes = client.get(f"/songs/{song}/renders/{job['id']}/takes").json()
    brian_takes = [t for t in takes if t["singer_id"] == singers["Brian"]]
    assert all(t["source_kind"] == "upload" for t in brian_takes)
    assert any(t["source_kind"] == "mock" for t in takes if t["singer_id"] != singers["Brian"])


def test_render_without_roles_is_rejected(client):
    song = client.post("/songs", json={"title": "Empty"}).json()["id"]
    section = client.post(
        f"/songs/{song}/sections", json={"section_type": "verse"}
    ).json()["id"]
    assert client.post(f"/songs/{song}/sections/{section}/render", json={}).status_code == 422
