"""Stage 11 exit criteria: vocal morph is behind an experimental flag; previews
carry quality flags; an unreliable morph cannot be committed.
"""

from __future__ import annotations

import hashlib
import io

import numpy as np
import pytest
import soundfile as sf

from sr.config import get_settings


@pytest.fixture
def morph_on():
    s = get_settings()
    before = s.experimental_morph
    s.experimental_morph = True
    try:
        yield
    finally:
        s.experimental_morph = before


def _guide_bytes(seconds=4.0, sr=44100):
    t = np.linspace(0, seconds, int(sr * seconds), endpoint=False)
    mel = np.zeros_like(t)
    for i, f in enumerate([196.0, 220.0, 247.0, 220.0, 196.0]):
        seg = (t >= i * 0.8) & (t < (i + 1) * 0.8)
        mel[seg] = np.sin(2 * np.pi * f * t[seg])
    buf = io.BytesIO()
    sf.write(buf, (0.4 * mel).astype("float32"), sr, format="WAV")
    return buf.getvalue()


def _make_section(client, *, mode: str):
    """mode='placeholder' -> both singers render deterministic placeholders whose
    envelopes track (a smooth morph). mode='mismatch' -> each singer converts the
    guide with a very different voice profile, decorrelating the performances.
    """
    client.get("/bands").json()
    a = client.post("/singers", json={"name": "Brian"}).json()["id"]
    b = client.post("/singers", json={"name": "Pete"}).json()["id"]
    for sid, f0, bright in ((a, 110.0, -0.6), (b, 245.0, 0.6)):
        client.patch(f"/singers/{sid}", json={"consent_generation": True})
        if mode == "mismatch":
            client.patch(
                f"/singers/{sid}/voice-model",
                json={"median_f0": f0, "brightness": bright},
            )
    song = client.post("/songs", json={"title": "M", "seed": 2}).json()["id"]
    sec = client.post(
        f"/songs/{song}/sections",
        json={"section_type": "bridge", "start_time": 0, "end_time": 4},
    ).json()["id"]
    if mode == "mismatch":
        client.post(
            f"/songs/{song}/sections/{sec}/guide",
            files={"file": ("g.wav", _guide_bytes(), "audio/wav")},
        )
    return song, sec, a, b


def test_morph_is_gated_off_by_default(client):
    assert client.get("/experimental").json() == {"morph_enabled": False}
    song, sec, a, b = _make_section(client, mode="placeholder")
    r = client.post(
        f"/sections/{sec}/morphs",
        json={"section_id": sec, "from_singer_id": a, "to_singer_id": b},
    )
    assert r.status_code == 403


def test_preview_is_deterministic_with_quality_flags(client, morph_on):
    song, sec, a, b = _make_section(client, mode="mismatch")
    morph = client.post(
        f"/sections/{sec}/morphs",
        json={"section_id": sec, "from_singer_id": a, "to_singer_id": b,
              "curve": "equal_power", "start_frac": 0.25, "end_frac": 0.75},
    ).json()

    def preview():
        j = client.post(f"/morphs/{morph['id']}/preview", json={}).json()
        assert j["status"] == "succeeded", j.get("error")
        q = j["result_json"]["quality"]
        assert set(q) >= {"score", "flags", "usable"}
        aid = j["result_json"]["preview_asset_id"]
        return q, hashlib.sha256(
            client.get(f"/songs/{song}/assets/{aid}/download").content
        ).hexdigest()

    q1, sha1 = preview()
    q2, sha2 = preview()
    assert sha1 == sha2  # deterministic
    assert q1 == q2


def test_unreliable_morph_cannot_be_committed(client, morph_on):
    # two very different voice profiles converting the guide -> performances that
    # don't track each other -> the blend would pump
    song, sec, a, b = _make_section(client, mode="mismatch")
    morph = client.post(
        f"/sections/{sec}/morphs",
        json={"section_id": sec, "from_singer_id": a, "to_singer_id": b},
    ).json()
    j = client.post(f"/morphs/{morph['id']}/preview", json={}).json()
    q = j["result_json"]["quality"]
    assert q["usable"] is False
    assert "poor_alignment" in q["flags"]

    r = client.post(f"/morphs/{morph['id']}/commit")
    assert r.status_code == 409


def test_reliable_morph_commits(client, morph_on):
    # deterministic placeholders share an envelope contour -> a smooth morph
    song, sec, a, b = _make_section(client, mode="placeholder")
    morph = client.post(
        f"/sections/{sec}/morphs",
        json={"section_id": sec, "from_singer_id": a, "to_singer_id": b,
              "curve": "scurve", "start_frac": 0.3, "end_frac": 0.7},
    ).json()
    j = client.post(f"/morphs/{morph['id']}/preview", json={}).json()
    q = j["result_json"]["quality"]
    assert q["usable"] is True, q
    committed = client.post(f"/morphs/{morph['id']}/commit").json()
    assert committed["committed"] is True
