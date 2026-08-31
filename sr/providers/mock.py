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
    AudioAnalysisProvider,
    MasteringProvider,
    MusicGenerationProvider,
    ProviderResult,
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
    version = "mock-music-0.1.0"

    def generate(self, *, prompt: str, params: dict[str, Any], seed: int) -> ProviderResult:
        duration = float(params.get("duration", 8.0))
        key = f"generated/mock/music_{derive_seed(seed, 'music', prompt)}.wav"
        out = _write_asset(key, duration)
        out["asset_type"] = "section_render"
        return self._result(
            outputs=[out],
            metadata={"prompt": prompt, "seed": seed, "params": params},
            logs=[f"mock music: {duration}s from prompt {prompt!r}"],
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

    def separate(self, *, source_asset: str, params: dict[str, Any]) -> ProviderResult:
        duration = float(params.get("duration", 8.0))
        stems = ["stem_drums", "stem_bass", "stem_guitars", "stem_lead_vocal", "stem_instrumental"]
        outputs = []
        for st in stems:
            key = f"stems/mock/{st}_{derive_seed(1, source_asset, st)}.wav"
            o = _write_asset(key, duration)
            o["asset_type"] = st
            outputs.append(o)
        return self._result(outputs=outputs, logs=[f"mock stems from {source_asset}"])


class MockAnalysisProvider(AudioAnalysisProvider):
    name = "mock"
    version = "mock-analysis-0.1.0"

    def analyze(self, *, source_asset: str) -> ProviderResult:
        s = derive_seed(1, source_asset)
        return self._result(
            metadata={
                "bpm": round(bounded_jitter(s, 90, 180), 1),
                "key": ["C", "D", "E", "F", "G", "A", "B"][s % 7],
                "duration": round(bounded_jitter(s ^ 3, 120, 240), 1),
                "loudness_lufs": round(bounded_jitter(s ^ 7, -16, -6), 1),
                "sections": ["intro", "verse", "chorus", "verse", "chorus", "bridge", "chorus"],
            },
            logs=[f"mock analysis of {source_asset}"],
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
