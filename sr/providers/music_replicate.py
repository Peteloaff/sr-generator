"""ReplicateMusicProvider - a real hosted text-to-music model via Replicate.

Uses Meta's MusicGen (replicate.com/meta/musicgen) through Replicate's hosted
inference API - no GPU to run or manage, billed per second of generation.

Set ``SR_MUSIC_PROVIDER=replicate`` and ``SR_REPLICATE_API_TOKEN`` (from
https://replicate.com/account/api-tokens). Does not support band-adapter
training (``trains_adapter = False``) - it's a generic prompt-conditioned
model, not one this app can fine-tune per band.
"""

from __future__ import annotations

import io
import time
from typing import Any

import numpy as np

from sr.common.dsp import SR
from sr.config import get_settings
from sr.providers.base import MusicGeneration, MusicGenerationProvider

_API = "https://api.replicate.com/v1"
_MODEL = "meta/musicgen"
_MAX_SECONDS = 30.0
_POLL_INTERVAL = 2.0
_POLL_TIMEOUT = 300.0
_TERMINAL = ("succeeded", "failed", "canceled")

# meta/musicgen is a community (not "official") Replicate model, so the
# owner/name prediction shorthand 404s - it needs the classic /predictions
# endpoint with an explicit version hash. Resolved once per process and
# cached; a redeploy/restart re-resolves it if the model updates.
_version_cache: dict[str, str] = {}


class ReplicateMusicProvider(MusicGenerationProvider):
    name = "replicate"
    version = "replicate-musicgen-0.1.0"
    trains_adapter = False

    def _token(self) -> str:
        token = get_settings().replicate_api_token
        if not token:
            raise RuntimeError(
                "SR_REPLICATE_API_TOKEN is not set - get one from "
                "https://replicate.com/account/api-tokens"
            )
        return token

    def _prompt_text(self, prompt: str, params: dict[str, Any]) -> str:
        bpm = params.get("bpm")
        key = params.get("key")
        extra = ", ".join(
            s
            for s in (
                f"{float(bpm):.0f} BPM" if bpm else None,
                f"key of {key}" if key else None,
            )
            if s
        )
        return f"{prompt}, {extra}" if extra else prompt

    def _resolve_version(self, client: Any, headers: dict[str, str]) -> str:
        cached = _version_cache.get(_MODEL)
        if cached:
            return cached
        r = client.get(f"{_API}/models/{_MODEL}", headers=headers)
        r.raise_for_status()
        version = (r.json().get("latest_version") or {}).get("id")
        if not version:
            raise RuntimeError(f"replicate model {_MODEL} has no latest_version")
        _version_cache[_MODEL] = version
        return version

    def generate(
        self, *, prompt: str, params: dict[str, Any], seed: int, adapter: dict[str, Any] | None
    ) -> MusicGeneration:
        import httpx  # noqa: PLC0415
        import soundfile as sf  # noqa: PLC0415

        duration = min(_MAX_SECONDS, max(1.0, float(params.get("duration") or 8.0)))
        text = self._prompt_text(prompt, params)
        headers = {"Authorization": f"Bearer {self._token()}"}
        # this app's seeds are derived (large hash-based ints); Replicate
        # requires a uint32, so fold it into range while staying deterministic.
        replicate_seed = int(seed) % (2**32)

        with httpx.Client(timeout=60) as client:
            version = self._resolve_version(client, headers)
            r = client.post(
                f"{_API}/predictions",
                headers=headers,
                json={
                    "version": version,
                    "input": {
                        "prompt": text,
                        "duration": int(round(duration)),
                        "model_version": get_settings().replicate_music_model_version,
                        "output_format": "wav",
                        "normalization_strategy": "peak",
                        "seed": replicate_seed,
                    },
                },
            )
            r.raise_for_status()
            pred = r.json()
            pred_id = pred["id"]

            deadline = time.monotonic() + _POLL_TIMEOUT
            while pred.get("status") not in _TERMINAL:
                if time.monotonic() > deadline:
                    raise TimeoutError(f"replicate prediction {pred_id} timed out")
                time.sleep(_POLL_INTERVAL)
                r = client.get(f"{_API}/predictions/{pred_id}", headers=headers)
                r.raise_for_status()
                pred = r.json()

            if pred["status"] != "succeeded":
                raise RuntimeError(
                    f"replicate music generation failed: {pred.get('error') or 'unknown error'}"
                )

            output = pred.get("output")
            audio_url = output[0] if isinstance(output, list) else output
            if not audio_url:
                raise RuntimeError("replicate music generation returned no output")
            audio_resp = client.get(audio_url)
            audio_resp.raise_for_status()

        data, rate = sf.read(io.BytesIO(audio_resp.content), dtype="float32", always_2d=True)
        if data.shape[1] == 1:
            data = np.repeat(data, 2, axis=1)
        elif data.shape[1] > 2:
            data = data[:, :2]

        return MusicGeneration(
            audio=np.ascontiguousarray(data, dtype=np.float32),
            sample_rate=rate or SR,
            provider=self.name,
            provider_version=str(pred.get("version") or self.version),
            metadata={"prompt": text, "duration": duration, "replicate_id": pred_id},
        )
