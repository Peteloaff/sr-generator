"""Deterministic largest-remainder allocation and percentage normalization.

Blueprint acceptance test: 70/20/10 with ensemble size 10 -> 7/2/1. Ties broken
by a stable key ordering so the result never depends on dict iteration order.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass


def normalize_weights(weights: Mapping[str, float], ndigits: int = 4) -> dict[str, float]:
    """Scale weights so they sum to 100. Empty / all-zero -> equal split."""
    keys = list(weights)
    if not keys:
        return {}
    total = sum(max(0.0, float(w)) for w in weights.values())
    if total <= 0:
        share = round(100.0 / len(keys), ndigits)
        return {k: share for k in keys}
    return {k: round(max(0.0, float(weights[k])) / total * 100.0, ndigits) for k in keys}


@dataclass(frozen=True)
class Allocation:
    counts: dict[str, int]
    ensemble_size: int

    def as_takes(self) -> list[str]:
        """Flat list of keys, one entry per virtual take, stable order."""
        out: list[str] = []
        for key in sorted(self.counts):
            out.extend([key] * self.counts[key])
        return out


def largest_remainder_allocation(
    weights: Mapping[str, float],
    ensemble_size: int,
    *,
    tie_break_order: list[str] | None = None,
) -> Allocation:
    """Map weights to an integer count per key that sums to ``ensemble_size``.

    Deterministic: floor every ideal share, then hand out the remaining slots to
    the largest fractional remainders, breaking ties by ``tie_break_order``
    (defaults to sorted key order).
    """
    keys = list(weights)
    if ensemble_size <= 0 or not keys:
        return Allocation({k: 0 for k in keys}, max(0, ensemble_size))

    norm = normalize_weights(weights)
    order = tie_break_order or sorted(keys)
    rank = {k: i for i, k in enumerate(order)}

    ideal = {k: norm[k] / 100.0 * ensemble_size for k in keys}
    floors = {k: int(ideal[k]) for k in keys}
    assigned = sum(floors.values())
    remaining = ensemble_size - assigned

    remainders = sorted(
        keys,
        key=lambda k: (-(ideal[k] - floors[k]), rank.get(k, len(order))),
    )
    for i in range(remaining):
        floors[remainders[i % len(remainders)]] += 1

    return Allocation(floors, ensemble_size)
