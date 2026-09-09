"""Training a singer from a full song (vocal separation) + the one-shot endpoint."""

from __future__ import annotations

import io

import numpy as np
import soundfile as sf


def _song_bytes(seconds: float = 3.0, rate: int = 44100) -> bytes:
    t = np.linspace(0, seconds, int(seconds * rate), endpoint=False)
    # a "vocal" up the middle + a wide "band"
    vox = 0.4 * np.sin(2 * np.pi * 200 * t) * (0.5 + 0.5 * np.sin(2 * np.pi * 4 * t))
    band = 0.3 * np.sign(np.sin(2 * np.pi * 110 * t))
    left = vox + band
    right = vox - band
    buf = io.BytesIO()
    sf.write(buf, np.stack([left, right], axis=1).astype(np.float32), rate, format="WAV")
    return buf.getvalue()


def test_upload_a_full_song_and_train(client):
    sid = client.post("/singers", json={"name": "Sep"}).json()["id"]
    client.patch(f"/singers/{sid}", json={"consent_training": True})

    r = client.post(
        f"/singers/{sid}/samples",
        files={"file": ("track.wav", _song_bytes(), "audio/wav")},
        data={"full_song": "true"},
    )
    assert r.status_code == 201
    assert r.json()["asset_type"] == "singer_song"

    job = client.post(f"/singers/{sid}/voice-model/train").json()
    done = client.post(f"/jobs/{job['id']}/wait", params={"timeout": 120}).json()
    assert done["status"] == "succeeded", done.get("error")
    assert done["result_json"]["separated_from_songs"] == 1

    vm = client.get(f"/singers/{sid}/voice-model").json()
    assert vm["training_status"] == "ready"
    assert "median_f0" in vm["voice_profile"]


def test_create_singer_from_song_one_shot(client):
    job = client.post(
        "/singers/from-song",
        files={"file": ("demo.wav", _song_bytes(), "audio/wav")},
        data={"name": "Ripped"},
    ).json()
    done = client.post(f"/jobs/{job['id']}/wait", params={"timeout": 120}).json()
    assert done["status"] == "succeeded", done.get("error")

    singer = next(s for s in client.get("/singers").json() if s["name"] == "Ripped")
    assert singer["consent_generation"] is True
    vm = client.get(f"/singers/{singer['id']}/voice-model").json()
    assert vm["training_status"] == "ready"

    # a separated-vocal asset is kept with lineage
    samples = client.get(f"/singers/{singer['id']}/samples").json()
    assert any(a["asset_type"] == "singer_song" for a in samples)

    dup = client.post(
        "/singers/from-song",
        files={"file": ("demo.wav", _song_bytes(), "audio/wav")},
        data={"name": "Ripped"},
    )
    assert dup.status_code == 409


def test_isolated_clip_still_works_without_separation(client):
    sid = client.post("/singers", json={"name": "Clip"}).json()["id"]
    client.patch(f"/singers/{sid}", json={"consent_training": True})
    client.post(
        f"/singers/{sid}/samples",
        files={"file": ("v.wav", _song_bytes(1.5), "audio/wav")},
    )
    job = client.post(f"/singers/{sid}/voice-model/train").json()
    done = client.post(f"/jobs/{job['id']}/wait", params={"timeout": 60}).json()
    assert done["status"] == "succeeded"
    assert done["result_json"]["separated_from_songs"] == 0
