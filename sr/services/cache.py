"""Content-addressed cache for expensive renders (voice conversions).

The cache is **filesystem-first**: a conversion is a WAV at a deterministic key,
written before the render transaction that requested it commits. So a job retry
after a rollback still finds the file and skips the work - without needing a
second DB transaction (which SQLite's single writer cannot grant concurrently).
The ``RenderCache`` row is best-effort bookkeeping (hit counts, provider version).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from sr.common.dsp import SR
from sr.common.storage import get_storage
from sr.models.render_cache import RenderCache


def key_for(*parts: object) -> str:
    h = hashlib.sha256()
    for p in parts:
        h.update(b"\x1f")
        h.update(json.dumps(p, sort_keys=True, default=str).encode())
    return h.hexdigest()[:64]


def hash_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()[:32]


def _file_key(cache_key: str, kind: str) -> str:
    return f"cache/{kind}/{cache_key[:2]}/{cache_key}.wav"


def lookup(
    cache_key: str, *, kind: str = "voice_conversion", db: Session | None = None
) -> str | None:
    """Return the storage key of the cached WAV if it exists on disk, else None."""
    fk = _file_key(cache_key, kind)
    if not get_storage().exists(fk):
        return None
    if db is not None:
        row = db.scalar(select(RenderCache).where(RenderCache.cache_key == cache_key))
        if row is not None:
            row.hits += 1
    return fk


def store(
    cache_key: str,
    *,
    kind: str,
    provider: str,
    provider_version: str,
    samples: np.ndarray,
    sample_rate: int = SR,
    db: Session | None = None,
) -> str:
    fk = _file_key(cache_key, kind)
    stereo = samples if samples.ndim == 2 else np.stack([samples, samples], axis=1)
    get_storage().save_wav(fk, stereo.astype(np.float32), sample_rate)
    if db is not None and db.scalar(
        select(RenderCache).where(RenderCache.cache_key == cache_key)
    ) is None:
        db.add(
            RenderCache(
                cache_key=cache_key, kind=kind, provider=provider,
                provider_version=provider_version, file_path=fk,
                duration=round(len(samples) / sample_rate, 3),
            )
        )
    return fk
