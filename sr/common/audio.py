"""Audio probing, canonicalization, and waveform peaks.

Uses the ffmpeg binary bundled with ``imageio-ffmpeg`` - no system install. All
uploads are decoded to a canonical 16-bit 44.1k PCM WAV for analysis; the
original file is always kept too.
"""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

import imageio_ffmpeg
import numpy as np

from sr.common.storage import Storage

FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
CANONICAL_RATE = 44100
SUPPORTED_SUFFIXES = {
    ".wav", ".mp3", ".flac", ".m4a", ".aac", ".ogg", ".opus", ".aiff", ".aif", ".wma",
    ".webm", ".mp4", ".mkv",  # in-browser MediaRecorder output (opus in webm/mp4)
}

_DUR_RE = re.compile(r"Duration:\s*(\d+):(\d+):(\d+\.\d+)")
_STREAM_RE = re.compile(r"Audio:.*?,\s*(\d+)\s*Hz,\s*([^,]+),")


@dataclass(frozen=True)
class AudioInfo:
    duration: float
    sample_rate: int
    channels: int


def _run(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run([FFMPEG, *args], capture_output=True, check=True)


def probe(path: Path) -> AudioInfo:
    """Duration / sample rate / channels, parsed from ffmpeg's banner."""
    proc = subprocess.run(
        [FFMPEG, "-hide_banner", "-i", str(path)], capture_output=True, text=True
    )
    text = proc.stderr
    duration = 0.0
    if (m := _DUR_RE.search(text)) is not None:
        h, mm, ss = m.groups()
        duration = int(h) * 3600 + int(mm) * 60 + float(ss)
    sample_rate, channels = CANONICAL_RATE, 2
    if (m := _STREAM_RE.search(text)) is not None:
        sample_rate = int(m.group(1))
        layout = m.group(2).strip()
        channels = {"mono": 1, "stereo": 2}.get(layout, 2)
        if (cm := re.match(r"(\d+)", layout)) is not None:
            channels = int(cm.group(1))
    return AudioInfo(round(duration, 3), sample_rate, channels)


def _decode_pcm(path: Path, *, mono: bool, rate: int = CANONICAL_RATE) -> np.ndarray:
    ch = "1" if mono else "2"
    proc = _run(
        ["-v", "quiet", "-i", str(path), "-ac", ch, "-ar", str(rate),
         "-f", "s16le", "-acodec", "pcm_s16le", "-"]
    )
    arr = np.frombuffer(proc.stdout, dtype="<i2").astype(np.float32) / 32768.0
    return arr if mono else arr.reshape(-1, 2)


def to_canonical_wav(src: Path, dst: Path) -> AudioInfo:
    """Write a 16-bit 44.1k WAV copy of ``src`` at ``dst``; return its info."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    _run(["-y", "-v", "quiet", "-i", str(src), "-ar", str(CANONICAL_RATE),
          "-acodec", "pcm_s16le", str(dst)])
    return probe(dst)


@dataclass(frozen=True)
class IngestResult:
    original_key: str
    canonical_key: str
    peaks_key: str
    info: AudioInfo


def ingest_upload(
    storage: Storage, base_key: str, filename: str, data: bytes
) -> IngestResult:
    """Store an uploaded audio file: original + canonical WAV + waveform peaks.

    ``base_key`` is a storage-relative directory. Raises ValueError on an
    unsupported suffix or an undecodable file.
    """
    suffix = Path(filename or "upload").suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise ValueError(
            f"unsupported audio type {suffix!r}; supported: {sorted(SUPPORTED_SUFFIXES)}"
        )

    original_key = f"{base_key}/original{suffix}"
    canonical_key = f"{base_key}/canonical.wav"
    peaks_key = f"{base_key}/peaks.json"
    storage.write_bytes(original_key, data)
    try:
        src = storage.ensure_local(original_key)
        canonical = storage.path_for(canonical_key)
        info = to_canonical_wav(src, canonical)
        storage.persist(canonical_key)
        peaks = waveform_peaks(canonical)
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"could not decode audio: {exc}") from exc
    storage.write_text(peaks_key, json.dumps(peaks))
    return IngestResult(original_key, canonical_key, peaks_key, info)


def waveform_peaks(path: Path, buckets: int = 1200) -> list[list[float]]:
    """Downsample to ``buckets`` [min, max] pairs in [-1, 1] for display."""
    mono = _decode_pcm(path, mono=True)
    if mono.size == 0:
        return []
    buckets = max(1, min(buckets, mono.size))
    edges = np.linspace(0, mono.size, buckets + 1, dtype=int)
    peaks: list[list[float]] = []
    for i in range(buckets):
        seg = mono[edges[i] : edges[i + 1]]
        if seg.size == 0:
            peaks.append([0.0, 0.0])
        else:
            peaks.append([round(float(seg.min()), 4), round(float(seg.max()), 4)])
    return peaks
