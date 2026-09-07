"""Stage 13: player style-model training (Demucs/bandsplit separation + analysis)."""

from __future__ import annotations

import io

import numpy as np
import pytest
import soundfile as sf

from sr.common import playerstyle


def _band_mix(seconds: float = 4.0, rate: int = 44100, *, busy: bool = False) -> bytes:
    """A crude synthetic band: kick+snare, a bass line, and a buzzy guitar chord."""
    t = np.linspace(0, seconds, int(rate * seconds), endpoint=False)
    beat = 0.5
    drums = np.zeros_like(t)
    for i in range(int(seconds / beat)):
        s = int(i * beat * rate)
        env = np.exp(-np.arange(rate // 8) / (rate * 0.02))
        tone = np.sin(2 * np.pi * 60 * np.arange(rate // 8) / rate)
        drums[s : s + len(env)] += (tone * env)[: max(0, len(drums) - s)][: len(env)]
    bass = 0.4 * np.sign(np.sin(2 * np.pi * 82.4 * t))
    gtr = 0.3 * np.sign(np.sin(2 * np.pi * 220 * t)) * (1.0 if busy else 0.6)
    mix = np.clip(0.6 * drums + 0.6 * bass + 0.6 * gtr, -1, 1).astype(np.float32)
    buf = io.BytesIO()
    sf.write(buf, np.stack([mix, mix], axis=1), rate, format="WAV")
    return buf.getvalue()


def _player(client, name="Dave", role="lead_guitar", **consent):
    pid = client.post("/players", json={"name": name, "role": role}).json()["id"]
    if consent:
        client.patch(f"/players/{pid}", json=consent)
    return pid


def test_profile_is_deterministic_and_bounded():
    rng = np.random.default_rng(0)
    stem = (0.3 * rng.standard_normal((44100 * 3, 2))).astype(np.float32)
    a = playerstyle.analyze(stem, "drums", bpm=120)
    b = playerstyle.analyze(stem, "drums", bpm=120)
    assert a.to_dict() == b.to_dict()
    d = a.to_dict()
    for k in ("drive", "attack", "sustain", "busyness", "dynamics", "syncopation", "swing"):
        assert 0.0 <= d[k] <= 1.0
    assert -1.0 <= d["brightness"] <= 1.0


def test_blend_averages_profiles():
    p1 = playerstyle.StyleProfile(role="bass", drive=0.2, register_hz=100.0)
    p2 = playerstyle.StyleProfile(role="bass", drive=0.8, register_hz=400.0)
    out = playerstyle.blend([p1, p2])
    assert out.role == "bass"
    assert out.drive == pytest.approx(0.5)
    assert 190 < out.register_hz < 210  # geometric mean of 100 and 400


def test_train_player_end_to_end(client):
    pid = _player(client, consent_training=True)
    for i in range(2):
        client.post(
            f"/players/{pid}/samples",
            files={"file": (f"song{i}.wav", _band_mix(busy=bool(i)), "audio/wav")},
        )
    assert len(client.get(f"/players/{pid}/samples").json()) == 2

    job = client.post(f"/players/{pid}/style-model/train").json()
    done = client.post(f"/jobs/{job['id']}/wait").json()
    assert done["status"] == "succeeded", done.get("error")

    sm = client.get(f"/players/{pid}/style-model").json()
    assert sm["training_status"] == "ready"
    assert sm["training_samples"] == 2
    assert sm["style_model_provider"] == "local_dsp"
    assert sm["style_profile"]["role"] == "lead_guitar"
    assert "drive" in sm["style_profile"]
    assert done["result_json"]["separation_provider"] == "bandsplit"

    # the player's separated instrument is kept as an asset with lineage
    assets = client.get(f"/players/{pid}/samples").json()
    assert all(a["player_id"] == pid for a in assets)


def test_train_needs_consent(client):
    pid = _player(client)  # no consent
    client.post(f"/players/{pid}/samples", files={"file": ("s.wav", _band_mix(), "audio/wav")})
    assert client.post(f"/players/{pid}/style-model/train").status_code == 403


def test_train_needs_samples(client):
    pid = _player(client, consent_training=True)
    assert client.post(f"/players/{pid}/style-model/train").status_code == 422


def test_manual_style_patch_marks_ready(client):
    pid = _player(client, name="Manual Mike", role="bass")
    r = client.patch(f"/players/{pid}/style-model", json={"drive": 0.1, "attack": 0.9})
    assert r.status_code == 200
    body = r.json()
    assert body["training_status"] == "ready"
    assert body["style_model_provider"] == "manual"
    assert body["style_profile"]["drive"] == 0.1
    assert body["style_profile"]["role"] == "bass"
