"""Stage 3: singer voice-model setup workflow + consent on training."""

from __future__ import annotations


def _singer(client, name="Brian", **consent):
    sid = client.post("/singers", json={"name": name}).json()["id"]
    if consent:
        client.patch(f"/singers/{sid}", json=consent)
    return sid


def test_train_from_samples_produces_a_profile(client, sample_wav):
    sid = _singer(client, consent_training=True)
    with sample_wav.open("rb") as fh:
        r = client.post(f"/singers/{sid}/samples", files={"file": ("s.wav", fh, "audio/wav")})
    assert r.status_code == 201 and r.json()["asset_type"] == "singer_sample"

    job = client.post(f"/singers/{sid}/voice-model/train").json()
    done = client.post(f"/jobs/{job['id']}/wait").json()
    assert done["status"] == "succeeded"

    vm = client.get(f"/singers/{sid}/voice-model").json()
    assert vm["training_status"] == "ready"
    assert vm["training_samples"] == 1
    assert vm["voice_model_provider"] == "local_dsp"
    assert "median_f0" in vm["voice_profile"]


def test_train_without_consent_is_403(client, sample_wav):
    sid = _singer(client)  # no consent
    with sample_wav.open("rb") as fh:
        client.post(f"/singers/{sid}/samples", files={"file": ("s.wav", fh, "audio/wav")})
    assert client.post(f"/singers/{sid}/voice-model/train").status_code == 403


def test_train_without_samples_is_422(client):
    sid = _singer(client, consent_training=True)
    assert client.post(f"/singers/{sid}/voice-model/train").status_code == 422


def test_manual_profile_marks_model_ready(client):
    sid = _singer(client)
    r = client.patch(
        f"/singers/{sid}/voice-model",
        json={"median_f0": 240.0, "brightness": 0.4, "breathiness": 0.2},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["training_status"] == "ready"
    assert body["voice_model_provider"] == "manual"
    assert body["voice_profile"]["median_f0"] == 240.0
    assert body["voice_profile"]["brightness"] == 0.4


def test_samples_can_be_listed_and_deleted(client, sample_wav):
    sid = _singer(client)
    with sample_wav.open("rb") as fh:
        aid = client.post(
            f"/singers/{sid}/samples", files={"file": ("s.wav", fh, "audio/wav")}
        ).json()["id"]
    assert len(client.get(f"/singers/{sid}/samples").json()) == 1
    assert client.delete(f"/singers/{sid}/samples/{aid}").status_code == 204
    assert client.get(f"/singers/{sid}/samples").json() == []
