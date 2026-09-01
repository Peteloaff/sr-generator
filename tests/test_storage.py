"""The storage abstraction works against an S3-compatible object store, and the
render pipeline is agnostic to which backend is configured (Supabase Storage in
production, local filesystem in dev/tests).
"""

from __future__ import annotations

import contextlib

import numpy as np
import pytest

boto3 = pytest.importorskip("boto3")
moto = pytest.importorskip("moto")

from sr.common import storage as storage_mod  # noqa: E402
from sr.config import get_settings  # noqa: E402

_BUCKET = "sr-audio-test"


@pytest.fixture
def s3_storage(tmp_path):
    from moto import mock_aws

    with mock_aws():
        boto3.client("s3", region_name="us-east-1").create_bucket(Bucket=_BUCKET)
        s = get_settings()
        saved = {
            k: getattr(s, k)
            for k in ("storage_backend", "s3_endpoint_url", "s3_region", "s3_bucket",
                      "s3_access_key_id", "s3_secret_access_key", "s3_workdir")
        }
        s.storage_backend = "s3"
        s.s3_endpoint_url = "https://s3.us-east-1.amazonaws.com"
        s.s3_region = "us-east-1"
        s.s3_bucket = _BUCKET
        s.s3_access_key_id = "testing"
        s.s3_secret_access_key = "testing"
        s.s3_workdir = str(tmp_path / "work")
        storage_mod.reset_storage_cache()
        try:
            yield storage_mod.get_storage()
        finally:
            for k, v in saved.items():
                setattr(s, k, v)
            storage_mod.reset_storage_cache()


def test_object_store_round_trips_bytes_wav_and_listing(s3_storage):
    st = s3_storage
    st.write_text("meta/info.json", '{"a":1}')
    assert st.exists("meta/info.json")
    assert st.read_text("meta/info.json") == '{"a":1}'

    audio = (np.random.default_rng(0).standard_normal((2000, 2)) * 0.2).astype(np.float32)
    st.save_wav("renders/x/master.wav", audio)
    assert st.exists("renders/x/master.wav")

    # a fresh client with an empty scratch dir must still be able to read it back
    storage_mod.reset_storage_cache()
    st2 = storage_mod.get_storage()
    with contextlib.suppress(FileNotFoundError):
        st2.path_for("renders/x/master.wav").unlink()
    back = st2.read_stereo("renders/x/master.wav")
    assert back.shape[0] == 2000

    keys = st2.list("renders/")
    assert "renders/x/master.wav" in keys

    st2.delete("renders/x/master.wav")
    assert not st2.exists("renders/x/master.wav")


def test_full_render_works_on_the_object_store(client, s3_storage):
    """A section render with S3 storage produces downloadable stems + a master."""
    client.get("/bands").json()
    sid = client.post("/singers", json={"name": "Cloud"}).json()["id"]
    client.patch(f"/singers/{sid}", json={"consent_generation": True})
    client.patch(f"/singers/{sid}/voice-model", json={"median_f0": 140.0})

    song = client.post("/songs", json={"title": "Cloud song", "seed": 3}).json()["id"]
    section = client.post(
        f"/songs/{song}/sections",
        json={"section_type": "chorus", "start_time": 0, "end_time": 3},
    ).json()["id"]
    client.post(
        f"/sections/{section}/roles",
        json={"role_type": "lead", "assignments": [{"singer_id": sid}]},
    )
    job = client.post(f"/songs/{song}/sections/{section}/render", json={}).json()
    job = client.post(f"/jobs/{job['id']}/wait", params={"timeout": 90}).json()
    assert job["status"] == "succeeded", job.get("error")

    assets = client.get(f"/songs/{song}/assets").json()
    master = next(a for a in assets if a["asset_type"] == "master")
    wav = client.get(f"/songs/{song}/assets/{master['id']}/download").content
    assert wav[:4] == b"RIFF" and len(wav) > 1000
