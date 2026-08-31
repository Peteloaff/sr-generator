"""Deterministic seed derivation.

Every virtual take / variation gets a child seed derived from the parent seed
plus a stable set of string keys (singer id, role id, take index, ...). Same
inputs -> same seed -> same humanization values, forever. This is what makes
"identical inputs + provider version + seed reproduce the mix" true.

Seeds are masked to 63 bits so they fit a signed 64-bit integer everywhere they
are stored or used (SQLite/Postgres BIGINT, numpy int64, NumPy's Generator).
"""

from __future__ import annotations

import hashlib

_MASK63 = (1 << 63) - 1


def derive_seed(parent_seed: int, *keys: object) -> int:
    """Derive a stable 63-bit child seed from a parent seed and ordered keys."""
    h = hashlib.blake2b(digest_size=8)
    h.update(str(int(parent_seed)).encode())
    for k in keys:
        h.update(b"\x1f")
        h.update(str(k).encode())
    return int.from_bytes(h.digest(), "big") & _MASK63


def bounded_jitter(seed: int, low: float, high: float) -> float:
    """A single deterministic value in [low, high] from a seed (uniform)."""
    if high < low:
        low, high = high, low
    frac = (int(seed) & _MASK63) / float(_MASK63)
    return low + frac * (high - low)
