"""Stage 1: upload existing audio, get a waveform, section it."""

from __future__ import annotations


def test_upload_audio_and_waveform(client, sample_wav):
    song_id = client.post("/songs", json={"title": "Demo"}).json()["id"]

    with sample_wav.open("rb") as fh:
        r = client.post(
            f"/songs/{song_id}/audio", files={"file": ("clip.wav", fh, "audio/wav")}
        )
    assert r.status_code == 201
    asset = r.json()
    assert asset["asset_type"] == "upload"
    assert asset["duration"] == 1.5
    assert asset["sample_rate"] == 44100

    # song picks up duration from the first upload
    assert client.get(f"/songs/{song_id}").json()["duration"] == 1.5

    wf = client.get(f"/songs/{song_id}/assets/{asset['id']}/waveform").json()
    assert wf["buckets"] > 100
    assert all(-1.0 <= lo <= hi <= 1.0 for lo, hi in wf["peaks"])

    assert len(client.get(f"/songs/{song_id}/assets").json()) == 1


def test_unsupported_type_rejected(client):
    song_id = client.post("/songs", json={"title": "Demo"}).json()["id"]
    r = client.post(
        f"/songs/{song_id}/audio", files={"file": ("notes.txt", b"hello", "text/plain")}
    )
    assert r.status_code == 415
