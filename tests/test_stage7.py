"""Stage 7 exit criteria: repeatable band-specific instrumental sections that
are useful in the band workflow, with no coupling to the model provider."""

from __future__ import annotations

import hashlib
import io

import numpy as np
import pytest
import soundfile as sf

from sr.common.analysis import estimate_bpm
from sr.common.dsp import SR


def _track(path, bpm=124.0, notes=(220.0, 261.63, 329.63), seconds=26.0):
    t = np.arange(int(seconds * SR)) / SR
    chord = sum(0.12 * np.sin(2 * np.pi * f * t) for f in notes)
    drum = np.zeros_like(t)
    for b in np.arange(0, seconds, 60 / bpm):
        i = int(b * SR)
        rng = np.random.default_rng(int(b * 7))
        drum[i : i + 220] += np.exp(-np.linspace(0, 10, 220)) * rng.standard_normal(220) * 0.35
    m = (chord + drum * 0.5).astype(np.float32)
    sf.write(path, np.stack([m, m * 0.92], axis=1), SR)


@pytest.fixture
def trained_band(client, tmp_path):
    cat = tmp_path / "cat"
    cat.mkdir()
    _track(cat / "a.wav", 124.0, (220.0, 261.63, 329.63))
    _track(cat / "b.wav", 124.0, (196.0, 246.94, 293.66))
    _track(cat / "c.wav", 120.0, (261.63, 329.63, 392.0))
    band = client.get("/bands").json()[0]["id"]
    client.post(
        f"/bands/{band}/references/import-folder",
        json={"path": str(cat), "recursive": False},
    )
    for r in client.get(f"/bands/{band}/references").json():
        if r["quality_json"]["passed"]:
            client.patch(f"/references/{r['id']}", json={"approved_for_training": True})
    job = client.post(f"/bands/{band}/adapters/train", json={"name": "band"}).json()
    assert job["status"] == "succeeded"
    adapter = client.get(f"/bands/{band}/adapters").json()[0]
    return band, adapter


def test_adapter_is_distilled_from_the_dna(client, trained_band):
    _band, adapter = trained_band
    spec = adapter["spec_json"]
    assert adapter["dataset_version"]
    assert set(spec["character"]) == {"brightness", "drum_busy", "drive"}
    assert 60 < spec["tempo_prior"] < 200
    assert spec["trained_from"]["references"] == 3


def test_generated_instrumental_is_repeatable_and_tempo_locked(client, trained_band):
    band, adapter = trained_band
    song = client.post(
        "/songs", json={"title": "Gen", "seed": 11, "bpm": 128, "key": "E minor"}
    ).json()["id"]
    section = client.post(
        f"/songs/{song}/sections",
        json={"section_type": "chorus", "start_time": 0, "end_time": 6},
    ).json()["id"]

    def generate():
        j = client.post(
            f"/songs/{song}/sections/{section}/generate-instrumental",
            json={"prompt": "chorus", "adapter_id": adapter["id"], "seed": 11},
        ).json()
        assert j["status"] == "succeeded"
        assert j["result_json"]["bpm"] == 128.0 and j["result_json"]["key"] == "E minor"
        bed = next(
            a for a in client.get(f"/songs/{song}/assets").json()
            if a["asset_type"] == "instrumental_bed" and a["generation_job_id"] == j["id"]
        )
        return client.get(f"/songs/{song}/assets/{bed['id']}/download").content

    a = generate()
    b = generate()
    assert hashlib.sha256(a).hexdigest() == hashlib.sha256(b).hexdigest()  # repeatable

    data, _ = sf.read(io.BytesIO(a), always_2d=True)
    assert estimate_bpm(data.mean(axis=1)) == pytest.approx(128, abs=8)  # tempo-locked


def test_generated_bed_feeds_the_render(client, trained_band):
    band, adapter = trained_band
    sid = client.post("/singers", json={"name": "Brian"}).json()["id"]
    client.patch(f"/singers/{sid}", json={"consent_generation": True})
    client.patch(f"/singers/{sid}/voice-model", json={"median_f0": 130.0})
    song = client.post("/songs", json={"title": "Gen2", "seed": 3, "bpm": 120}).json()["id"]
    section = client.post(
        f"/songs/{song}/sections",
        json={"section_type": "verse", "start_time": 0, "end_time": 5},
    ).json()["id"]

    client.post(
        f"/songs/{song}/sections/{section}/generate-instrumental",
        json={"prompt": "verse", "adapter_id": adapter["id"]},
    )
    client.post(
        f"/sections/{section}/roles",
        json={"role_type": "lead", "assignments": [{"singer_id": sid}]},
    )
    r = client.post(f"/songs/{song}/sections/{section}/render", json={}).json()
    assert r["status"] == "succeeded"
    kinds = {a["asset_type"] for a in client.get(f"/songs/{song}/assets").json()}
    assert {"stem_instrumental", "vocal_bus", "mix"} <= kinds


def test_provider_is_swappable(client, trained_band):
    """The API/job flow is identical whichever music provider is configured."""
    band, adapter = trained_band
    song = client.post("/songs", json={"title": "P", "seed": 1}).json()["id"]
    section = client.post(
        f"/songs/{song}/sections", json={"section_type": "verse", "end_time": 4}
    ).json()["id"]

    from sr.config import get_settings

    get_settings().music_provider = "mock"
    try:
        j = client.post(
            f"/songs/{song}/sections/{section}/generate-instrumental", json={"prompt": "x"}
        ).json()
        assert j["status"] == "succeeded"
        assert j["provider"] == "mock"
        assert any(
            a["asset_type"] == "instrumental_bed"
            for a in client.get(f"/songs/{song}/assets").json()
        )
    finally:
        get_settings().music_provider = "local_synth"
