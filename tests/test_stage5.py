"""Stage 5 exit criteria: import a demo, separate stems, replace a vocal section,
and export a new mix without touching the other sections."""

from __future__ import annotations

import numpy as np
import pytest
import soundfile as sf


@pytest.fixture
def cover_wav(tmp_path):
    sr = 44100
    t = np.linspace(0, 12, sr * 12, endpoint=False)
    voc = np.zeros_like(t)
    for i, f in enumerate([220, 247, 262, 294, 262, 247, 220, 196]):
        seg = (t >= i * 1.5) & (t < (i + 1) * 1.5)
        voc[seg] = 0.35 * np.sin(2 * np.pi * f * t[seg])
    li = 0.25 * np.sin(2 * np.pi * 110 * t)
    ri = 0.25 * np.sin(2 * np.pi * 110 * t + 0.5) + 0.15 * np.sin(2 * np.pi * 220 * t)
    p = tmp_path / "cover.wav"
    sf.write(p, np.stack([voc + li, voc + ri], axis=1).astype(np.float32), sr)
    return p


def _win(a, s, e, sr=44100):
    return a[int(s * sr) : int(e * sr)]


def test_import_separate_replace_assemble(client, cover_wav):
    sid = client.post("/singers", json={"name": "Brian"}).json()["id"]
    client.patch(f"/singers/{sid}", json={"consent_generation": True})
    client.patch(f"/singers/{sid}/voice-model", json={"median_f0": 130.0})

    song = client.post("/songs", json={"title": "Cover", "seed": 5}).json()["id"]
    with cover_wav.open("rb") as fh:
        assert client.post(
            f"/songs/{song}/audio", files={"file": ("c.wav", fh, "audio/wav")}
        ).status_code == 201

    sec_a = client.post(
        f"/songs/{song}/sections",
        json={"section_type": "verse", "start_time": 0, "end_time": 4},
    ).json()["id"]
    client.post(
        f"/songs/{song}/sections",
        json={"section_type": "chorus", "start_time": 4, "end_time": 8},
    )

    # separate
    j = client.post(f"/songs/{song}/separate").json()
    assert j["status"] == "succeeded"
    stems = client.get(f"/songs/{song}/stems").json()
    assert {s["asset_type"] for s in stems} == {"stem_lead_vocal", "stem_instrumental"}
    assert all(s["version"] == 1 for s in stems)

    # re-separate bumps the version
    client.post(f"/songs/{song}/separate")
    versions = {s["version"] for s in client.get(f"/songs/{song}/stems").json()}
    assert versions == {1, 2}

    # wire the separated stems into section A, add a role, render
    derived = client.post(f"/songs/{song}/sections/{sec_a}/use-derived-stems").json()
    assert {d["asset_type"] for d in derived} == {"guide_vocal", "instrumental_bed"}
    client.post(
        f"/sections/{sec_a}/roles",
        json={"role_type": "lead", "assignments": [{"singer_id": sid}]},
    )
    assert client.post(f"/songs/{song}/sections/{sec_a}/render", json={}).json()["status"] == (
        "succeeded"
    )

    # assemble the full song
    asm = client.post(f"/songs/{song}/assemble").json()
    assert asm["status"] == "succeeded"
    assert [r["section_id"] for r in asm["result_json"]["replaced"]] == [sec_a]

    mix = client.get(f"/songs/{song}/mixes").json()[0]
    new_bytes = client.get(f"/songs/{song}/assets/{mix['id']}/download").content
    tmp = cover_wav.parent / "assembled.wav"
    tmp.write_bytes(new_bytes)
    new, _ = sf.read(tmp)

    from sr.common.storage import get_storage

    orig_path = next(
        p for p in get_storage().root.rglob("canonical.wav")
        if song in str(p) and f"{song}/canonical.wav" in str(p).replace("\\", "/")
    )
    orig, _ = sf.read(orig_path)

    # section B (4-8s) was not replaced -> byte-identical
    assert np.array_equal(_win(new, 5.0, 7.5), _win(orig, 5.0, 7.5))
    # section A (0-4s) was replaced -> differs
    assert not np.allclose(_win(new, 1.0, 3.0), _win(orig, 1.0, 3.0), atol=1e-4)


def test_separate_without_upload_is_422(client):
    song = client.post("/songs", json={"title": "empty"}).json()["id"]
    assert client.post(f"/songs/{song}/separate").status_code == 422


def test_assemble_without_renders_fails_the_job(client, cover_wav):
    song = client.post("/songs", json={"title": "no-render"}).json()["id"]
    with cover_wav.open("rb") as fh:
        client.post(f"/songs/{song}/audio", files={"file": ("c.wav", fh, "audio/wav")})
    job = client.post(f"/songs/{song}/assemble").json()
    done = client.post(f"/jobs/{job['id']}/wait").json()
    assert done["status"] == "failed"
    assert "render a section" in (done["error"] or "")
