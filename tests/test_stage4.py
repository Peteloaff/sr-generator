"""Stage 4 exit criteria: harmony intervals, processing chain, and the A/B that
shows ensemble mode is measurably different from a naive gain stack."""

from __future__ import annotations

import pytest


@pytest.fixture
def stacked_section(client):
    singers = {}
    for n in ("Brian", "Pete", "Brad"):
        sid = client.post("/singers", json={"name": n}).json()["id"]
        client.patch(f"/singers/{sid}", json={"consent_generation": True})
        singers[n] = sid
    song = client.post("/songs", json={"title": "Stack", "seed": 42}).json()["id"]
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
            "role_type": "gang", "ensemble_size": 12, "width": 90,
            "humanize_timing_ms": 22, "humanize_pitch_cents": 9,
            "processing": [
                {"type": "deesser", "amount": 0.4},
                {"type": "compressor", "ratio": 3, "threshold_db": -20},
            ],
            "assignments": [
                {"singer_id": singers["Brian"], "weight_percent": 50},
                {"singer_id": singers["Pete"], "weight_percent": 30},
                {"singer_id": singers["Brad"], "weight_percent": 20},
            ],
        },
    )
    return song, section, singers


def test_harmony_intervals_land_at_the_right_pitch(client, stacked_section):
    song, section, singers = stacked_section
    role = client.post(
        f"/sections/{section}/roles",
        json={
            "role_type": "harmony", "ensemble_size": 2, "humanize_pitch_cents": 0,
            "assignments": [
                {"singer_id": singers["Pete"], "weight_percent": 50, "interval_semitones": 3},
                {"singer_id": singers["Brad"], "weight_percent": 50, "interval_semitones": 7},
            ],
        },
    ).json()

    job = client.post(f"/songs/{song}/sections/{section}/render", json={}).json()
    takes = client.get(f"/songs/{song}/renders/{job['id']}/takes").json()
    by_role = [t for t in takes if t["vocal_role_id"] == role["id"]]
    pitches = {t["singer_id"]: t["pitch_cents"] for t in by_role}
    assert pitches[singers["Pete"]] == pytest.approx(300.0, abs=1.0)
    assert pitches[singers["Brad"]] == pytest.approx(700.0, abs=1.0)


def test_flat_mode_removes_all_variation(client, stacked_section):
    song, section, _ = stacked_section
    job = client.post(
        f"/songs/{song}/sections/{section}/render", json={"mode": "flat"}
    ).json()
    takes = client.get(f"/songs/{song}/renders/{job['id']}/takes").json()
    assert all(
        t["timing_offset_ms"] == 0.0 and t["pan"] == 0.0 and t["pitch_cents"] == 0.0
        for t in takes
    )


def test_processing_chain_is_recorded_on_the_role_stem(client, stacked_section):
    song, section, _ = stacked_section
    client.post(f"/songs/{song}/sections/{section}/render", json={})
    role_stems = [
        a for a in client.get(f"/songs/{song}/assets").json()
        if a["asset_type"] == "role_stem"
    ]
    assert any("deesser" in (a["label"] or "") for a in role_stems)


def test_ab_shows_ensemble_is_clearly_different(client, stacked_section):
    song, section, _ = stacked_section
    ab = client.post(f"/songs/{song}/sections/{section}/ab", json={}).json()

    assert ab["verdict"]["ensemble_clearly_different"] is True
    assert ab["ensemble"]["width_ratio"] > ab["flat"]["width_ratio"] + 0.05
    assert ab["flat"]["stereo_correlation"] == pytest.approx(1.0, abs=0.02)
    assert ab["ensemble"]["stereo_correlation"] < 0.95
    assert ab["ensemble"]["mono_compat"] > 0.5  # no phase collapse

    # individual takes still exportable
    takes = client.get(f"/songs/{song}/renders/{ab['ensemble_job_id']}/takes").json()
    take_assets = [
        a for a in client.get(f"/songs/{song}/assets").json() if a["asset_type"] == "take_stem"
    ]
    assert len(take_assets) >= len(takes) > 0
    one = client.get(f"/songs/{song}/assets/{take_assets[0]['id']}/download")
    assert one.status_code == 200 and one.content[:4] == b"RIFF"
