"""Stage 6 exit criteria: folder import + analysis, dataset quality, and a
reproducible training manifest that refuses incomplete metadata."""

from __future__ import annotations

import numpy as np
import pytest
import soundfile as sf

from sr.common.dsp import SR
from sr.db import session_scope
from sr.models.band_reference import BandReference


def _write_track(path, bpm=120.0, notes=(220.0, 261.63, 329.63), seconds=26.0):
    t = np.arange(int(seconds * SR)) / SR
    chord = sum(0.12 * np.sin(2 * np.pi * f * t) for f in notes)
    drum = np.zeros_like(t)
    for b in np.arange(0, seconds, 60 / bpm):
        i = int(b * SR)
        rng = np.random.default_rng(int(b * 7))
        drum[i : i + 220] += np.exp(-np.linspace(0, 10, 220)) * rng.standard_normal(220) * 0.3
    mono = (chord + drum * 0.5).astype(np.float32)
    sf.write(path, np.stack([mono, mono * 0.9 + 0.02 * rng.standard_normal(len(mono))], axis=1), SR)


@pytest.fixture
def catalogue(tmp_path):
    d = tmp_path / "catalogue"
    d.mkdir()
    _write_track(d / "song_a.wav", 120.0, (220.0, 261.63, 329.63))
    _write_track(d / "song_b.wav", 96.0, (261.63, 329.63, 392.0))
    _write_track(d / "too_short.wav", 120.0, (220.0, 261.63, 329.63), seconds=8.0)
    return d


def _band(client):
    return client.get("/bands").json()[0]["id"]


def test_import_folder_analyses_every_track(client, catalogue):
    band = _band(client)
    job = client.post(
        f"/bands/{band}/references/import-folder",
        json={"path": str(catalogue), "recursive": False},
    ).json()
    assert job["status"] == "succeeded"
    assert job["result_json"]["created"] == 3

    refs = client.get(f"/bands/{band}/references").json()
    assert len(refs) == 3
    assert all(r["analysis_status"] == "ready" for r in refs)
    assert all(r["bpm"] and r["key"] for r in refs)

    short = next(r for r in refs if r["title"] == "too_short")
    assert short["quality_json"]["passed"] is False
    assert any("too short" in f for f in short["quality_json"]["flags"])


def test_import_dedups_by_content(client, catalogue):
    band = _band(client)
    client.post(
        f"/bands/{band}/references/import-folder",
        json={"path": str(catalogue), "recursive": False},
    )
    again = client.post(
        f"/bands/{band}/references/import-folder",
        json={"path": str(catalogue), "recursive": False},
    ).json()
    assert again["result_json"]["created"] == 0
    assert again["result_json"]["skipped_duplicates"] == 3


def test_manifest_is_reproducible_and_gates_incomplete_metadata(client, catalogue):
    band = _band(client)
    client.post(
        f"/bands/{band}/references/import-folder",
        json={"path": str(catalogue), "recursive": False},
    )
    good = [
        r for r in client.get(f"/bands/{band}/references").json()
        if r["quality_json"]["passed"]
    ]
    for r in good:
        assert client.patch(
            f"/references/{r['id']}", json={"approved_for_training": True}
        ).status_code == 200

    m1 = client.get(f"/bands/{band}/training-manifest").json()
    m2 = client.get(f"/bands/{band}/training-manifest").json()
    assert m1["dataset_version"] == m2["dataset_version"]  # reproducible
    assert m1["totals"]["count"] == len(good)

    snap = client.post(f"/bands/{band}/training-manifest").json()
    assert snap["dataset_version"] == m1["dataset_version"]

    # break one approved reference's metadata -> manifest must refuse
    with session_scope() as db:
        db.query(BandReference).filter(
            BandReference.id == good[0]["id"]
        ).update({"bpm": None})
    r = client.get(f"/bands/{band}/training-manifest")
    assert r.status_code == 409
    assert good[0]["id"] in [x["id"] for x in r.json()["detail"]["incomplete"]]


def test_cannot_approve_before_analysis(client, tmp_path):
    band = _band(client)
    p = tmp_path / "x.wav"
    _write_track(p)
    with p.open("rb") as fh:
        ref = client.post(
            f"/bands/{band}/references?analyze=false",
            files={"file": ("x.wav", fh, "audio/wav")},
        ).json()
    assert ref["analysis_status"] == "none"
    r = client.patch(f"/references/{ref['id']}", json={"approved_for_training": True})
    assert r.status_code == 422


def test_band_dna_aggregates_the_catalogue(client, catalogue):
    band = _band(client)
    client.post(
        f"/bands/{band}/references/import-folder",
        json={"path": str(catalogue), "recursive": False},
    )
    dna = client.get(f"/bands/{band}/dna").json()
    assert dna["references"]["analyzed"] == 3
    assert dna["bpm"]["n"] == 3
    assert dna["key_distribution"]
