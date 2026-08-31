"""Mock providers - the only providers that exist in Stage 0.

They produce real (silent) WAV files deterministically from the seed so the whole
job/asset/lineage pipeline can be exercised end to end without any AI model.
"""

from __future__ import annotations

import hashlib
import wave
from io import BytesIO
from pathlib import Path
from typing import Any

import numpy as np

from sr.common.seeds import bounded_jitter, derive_seed
from sr.common.storage import get_storage
from sr.providers.base import (
    AudioAnalysis,
    AudioAnalysisProvider,
    MasteringProvider,
    MusicGeneration,
    MusicGenerationProvider,
    ProviderResult,
    StemSeparation,
    StemSeparationProvider,
    TranscriptionProvider,
    VoiceConversion,
    VoiceProvider,
)

_SR = 22050


def _silent_wav_bytes(duration_s: float, *, sample_rate: int = _SR) -> bytes:
    frames = max(1, int(duration_s * sample_rate))
    buf = BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        w.writeframes(b"\x00\x00" * frames)
    return buf.getvalue()


def _write_asset(key: str, duration_s: float) -> dict[str, Any]:
    data = _silent_wav_bytes(duration_s)
    get_storage().write_bytes(key, data)
    return {
        "file_path": key,
        "sample_rate": _SR,
        "channels": 1,
        "duration": round(duration_s, 3),
        "bytes": len(data),
    }


class MockMusicProvider(MusicGenerationProvider):
    name = "mock"
    version = "mock-music-0.2.0"
    trains_adapter = False

    def generate(
        self, *, prompt: str, params: dict[str, Any], seed: int, adapter: dict[str, Any] | None
    ) -> MusicGeneration:
        from sr.common.dsp import SR

        duration = float(params.get("duration", 8.0))
        n = max(1, int(duration * SR))
        rng = np.random.default_rng(derive_seed(seed, "mock-music", prompt))
        sig = (rng.standard_normal(n).astype(np.float32) * 0.03)
        return MusicGeneration(
            audio=np.stack([sig, sig], axis=1),
            sample_rate=SR,
            provider=self.name,
            provider_version=self.version,
            metadata={"prompt": prompt, "seed": seed, "bpm": params.get("bpm"),
                      "key": params.get("key"), "adapter": bool(adapter)},
        )


class MockVoiceProvider(VoiceProvider):
    name = "mock"
    version = "mock-voice-0.2.0"
    trains = False

    def analyze(self, sample_paths: list[Path], *, singer_ref: str) -> dict[str, Any]:
        h = int.from_bytes(hashlib.blake2b(singer_ref.encode(), digest_size=8).digest(), "big")
        return {"median_f0": 120.0 + (h % 120), "tint": (h >> 8) % 7}

    def convert(
        self, *, guide_path: Path, profile: dict[str, Any], params: dict[str, Any], seed: int
    ) -> VoiceConversion:
        from sr.common import dsp

        stereo = dsp.load_stereo(guide_path)
        mono = stereo.mean(axis=1)
        detune = bounded_jitter(derive_seed(seed, "mock-voice"), -30, 30)
        mono = dsp.pitch_shift_cents(mono.reshape(-1, 1), detune)[:, 0]
        return VoiceConversion(
            samples=mono.astype(np.float32),
            sample_rate=dsp.SR,
            provider=self.name,
            provider_version=self.version,
            metadata={"detune_cents": round(detune, 2), "profile": profile},
        )


class MockStemProvider(StemSeparationProvider):
    name = "mock"
    version = "mock-stem-0.1.0"
    produces = ("stem_lead_vocal", "stem_instrumental")

    def separate(self, *, source_path: Path, params: dict[str, Any]) -> StemSeparation:
        from sr.common import dsp

        stereo = dsp.load_stereo(Path(source_path))
        # trivial split: centre -> "vocal", the rest -> "instrumental"
        mid = 0.5 * (stereo[:, 0] + stereo[:, 1])
        vocal = np.stack([mid, mid], axis=1).astype(np.float32)
        return StemSeparation(
            stems={"stem_lead_vocal": vocal, "stem_instrumental": (stereo - vocal)},
            sample_rate=dsp.SR,
            provider=self.name,
            provider_version=self.version,
            metadata={"note": "mock centre split"},
        )


class MockAnalysisProvider(AudioAnalysisProvider):
    name = "mock"
    version = "mock-analysis-0.1.0"

    def analyze(self, *, source_path: Path) -> AudioAnalysis:
        s = derive_seed(1, str(source_path))
        return AudioAnalysis(
            analysis={
                "bpm": round(bounded_jitter(s, 90, 180), 1),
                "key": {"key": ["C major", "A minor", "E minor", "G major"][s % 4]},
                "tuning": {"label": "A=440 (standard)", "cents": 0.0},
                "loudness_dbfs": round(bounded_jitter(s ^ 7, -16, -6), 1),
                "energy_curve": [round(bounded_jitter(s ^ i, 0.2, 1.0), 3) for i in range(16)],
                "structure": {"count": 3, "unique": ["A", "B"]},
                "embedding": [0.0] * 8,
                "duration": round(bounded_jitter(s ^ 3, 120, 240), 1),
            },
            provider=self.name,
            provider_version=self.version,
        )


class MockMasteringProvider(MasteringProvider):
    name = "mock"
    version = "mock-mastering-0.1.0"

    def master(self, *, mix_asset: str, params: dict[str, Any]) -> ProviderResult:
        duration = float(params.get("duration", 8.0))
        key = f"generated/mock/master_{derive_seed(1, mix_asset)}.wav"
        out = _write_asset(key, duration)
        out["asset_type"] = "master"
        return self._result(outputs=[out], logs=[f"mock master of {mix_asset} (stems untouched)"])


class MockTranscriptionProvider(TranscriptionProvider):
    name = "mock"
    version = "mock-transcription-0.1.0"

    def transcribe(self, *, source_asset: str) -> ProviderResult:
        return self._result(
            metadata={"lines": [], "words": []},
            logs=[f"mock transcription of {source_asset}"],
        )
