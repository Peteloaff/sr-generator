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


def test_browser_recording_webm_is_accepted(client, tmp_path):
    """MediaRecorder in the browser produces webm/opus - the app must ingest it."""
    import subprocess

    import numpy as np
    import soundfile as sf

    from sr.common.audio import FFMPEG

    wav = tmp_path / "tone.wav"
    t = np.linspace(0, 1.0, 44100, endpoint=False)
    sf.write(wav, (0.3 * np.sin(2 * np.pi * 200 * t)).astype("float32"), 44100)
    webm = tmp_path / "recording.webm"
    subprocess.run(
        [FFMPEG, "-y", "-v", "quiet", "-i", str(wav), "-c:a", "libopus", str(webm)],
        check=True,
    )

    singer = client.post("/singers", json={"name": "Recorder"}).json()["id"]
    with webm.open("rb") as fh:
        r = client.post(
            f"/singers/{singer}/samples",
            files={"file": ("recording.webm", fh, "audio/webm")},
        )
    assert r.status_code == 201, r.text
    assert r.json()["asset_type"] == "singer_sample"
    assert r.json()["duration"] > 0.5
