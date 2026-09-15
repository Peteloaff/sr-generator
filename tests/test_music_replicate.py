"""ReplicateMusicProvider: prompt building, polling, decoding, failure modes."""

from __future__ import annotations

import io

import httpx
import numpy as np
import pytest
import soundfile as sf

from sr.config import get_settings
from sr.providers import music_replicate
from sr.providers.music_replicate import ReplicateMusicProvider

_MODEL_INFO = {"latest_version": {"id": "671ac645ce5e552cc63a54a2bbff63fcf798043055d2dac5fc9e36a837eedcfb"}}


def _wav_bytes(seconds: float = 1.0, sr: int = 32000) -> bytes:
    n = int(seconds * sr)
    audio = (0.1 * np.sin(np.linspace(0, 440, n))).astype(np.float32)
    stereo = np.stack([audio, audio], axis=1)
    buf = io.BytesIO()
    sf.write(buf, stereo, sr, format="WAV")
    return buf.getvalue()


class _FakeResponse:
    def __init__(self, json_data=None, content=b"", status_code=200):
        self._json = json_data
        self.content = content
        self.status_code = status_code

    def json(self):
        return self._json

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("error", request=None, response=self)


@pytest.fixture(autouse=True)
def _token(monkeypatch):
    monkeypatch.setenv("SR_REPLICATE_API_TOKEN", "test-token")
    get_settings.cache_clear()
    music_replicate._version_cache.clear()
    yield
    get_settings.cache_clear()
    music_replicate._version_cache.clear()


def test_missing_token_raises(monkeypatch):
    monkeypatch.delenv("SR_REPLICATE_API_TOKEN", raising=False)
    get_settings.cache_clear()
    with pytest.raises(RuntimeError, match="SR_REPLICATE_API_TOKEN"):
        ReplicateMusicProvider().generate(prompt="test", params={}, seed=1, adapter=None)


def test_generate_polls_until_succeeded_and_decodes_audio(monkeypatch):
    calls = {"post": 0, "get": 0}
    wav = _wav_bytes()

    def fake_post(self, url, headers=None, json=None):
        calls["post"] += 1
        assert url.endswith("/predictions") and "models/" not in url
        assert json["version"] == _MODEL_INFO["latest_version"]["id"]
        assert json["input"]["duration"] == 8
        assert "120 BPM" in json["input"]["prompt"]
        assert "key of D minor" in json["input"]["prompt"]
        return _FakeResponse({"id": "abc123", "status": "starting"})

    def fake_get(self, url, headers=None):
        calls["get"] += 1
        if url.endswith("/models/meta/musicgen"):
            return _FakeResponse(_MODEL_INFO)
        if url.endswith("/predictions/abc123"):
            return _FakeResponse({"id": "abc123", "status": "succeeded",
                                   "output": "https://replicate.delivery/out.wav",
                                   "version": "abcd1234"})
        assert url == "https://replicate.delivery/out.wav"
        return _FakeResponse(content=wav)

    monkeypatch.setattr(httpx.Client, "post", fake_post)
    monkeypatch.setattr(httpx.Client, "get", fake_get)

    result = ReplicateMusicProvider().generate(
        prompt="sludge metal anthem",
        params={"duration": 8, "bpm": 120.3, "key": "D minor"},
        seed=42,
        adapter=None,
    )

    assert calls["post"] == 1
    assert calls["get"] == 3  # version resolve + one poll + one download
    assert result.provider == "replicate"
    assert result.provider_version == "abcd1234"
    assert result.audio.ndim == 2 and result.audio.shape[1] == 2
    assert result.audio.shape[0] > 0
    assert result.metadata["replicate_id"] == "abc123"


def test_generate_polls_multiple_times_before_success(monkeypatch):
    wav = _wav_bytes()
    statuses = iter(["starting", "processing", "succeeded"])

    def fake_post(self, url, headers=None, json=None):
        return _FakeResponse({"id": "xyz", "status": "starting"})

    def fake_get(self, url, headers=None):
        if url.endswith("/models/meta/musicgen"):
            return _FakeResponse(_MODEL_INFO)
        if url.endswith("/predictions/xyz"):
            status = next(statuses, "succeeded")
            body = {"id": "xyz", "status": status}
            if status == "succeeded":
                body["output"] = ["https://replicate.delivery/out.wav"]
                body["version"] = "v1"
            return _FakeResponse(body)
        return _FakeResponse(content=wav)

    monkeypatch.setattr(httpx.Client, "post", fake_post)
    monkeypatch.setattr(httpx.Client, "get", fake_get)
    monkeypatch.setattr("sr.providers.music_replicate._POLL_INTERVAL", 0.0)

    result = ReplicateMusicProvider().generate(
        prompt="test", params={"duration": 4}, seed=1, adapter=None,
    )
    assert result.audio.shape[0] > 0


def test_generate_raises_on_failed_prediction(monkeypatch):
    def fake_post(self, url, headers=None, json=None):
        return _FakeResponse({"id": "bad", "status": "starting"})

    def fake_get(self, url, headers=None):
        if url.endswith("/models/meta/musicgen"):
            return _FakeResponse(_MODEL_INFO)
        return _FakeResponse({"id": "bad", "status": "failed", "error": "nope"})

    monkeypatch.setattr(httpx.Client, "post", fake_post)
    monkeypatch.setattr(httpx.Client, "get", fake_get)

    with pytest.raises(RuntimeError, match="nope"):
        ReplicateMusicProvider().generate(
            prompt="test", params={}, seed=1, adapter=None,
        )


def test_duration_is_clamped_to_max():
    provider = ReplicateMusicProvider()
    text = provider._prompt_text("x", {"bpm": None, "key": None})
    assert text == "x"
    text2 = provider._prompt_text("x", {"bpm": 90, "key": "C major"})
    assert text2 == "x, 90 BPM, key of C major"
