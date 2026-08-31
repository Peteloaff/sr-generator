"""Mock providers - the only providers that exist in Stage 0.

They produce real (silent) WAV files deterministically from the seed so the whole
job/asset/lineage pipeline can be exercised end to end without any AI model.
"""

from __future__ import annotations

import wave
from io import BytesIO
from typing import Any

from sr.common.seeds import bounded_jitter, derive_seed
from sr.common.storage import get_storage
from sr.providers.base import (
    AudioAnalysisProvider,
    MasteringProvider,
    MusicGenerationProvider,
    ProviderResult,
    StemSeparationProvider,
    TranscriptionProvider,
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
    version = "mock-voice-0.1.0"

    def render(
        self, *, guide_asset: str | None, singer_ref: str, params: dict[str, Any], seed: int
    ) -> ProviderResult:
        duration = float(params.get("duration", 4.0))
        child = derive_seed(seed, "voice", singer_ref, params.get("take_index", 0))
        key = f"generated/mock/voice_{singer_ref}_{child}.wav"
        out = _write_asset(key, duration)
        out["asset_type"] = "stem_lead_vocal"
        return self._result(
            outputs=[out],
            metadata={
                "singer_ref": singer_ref,
                "guide_asset": guide_asset,
                "seed": child,
                "timing_jitter_ms": round(bounded_jitter(child, -20, 20), 2),
                "pitch_jitter_cents": round(bounded_jitter(child ^ 1, -8, 8), 2),
            },
            logs=[f"mock voice: singer={singer_ref} {duration}s"],
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
