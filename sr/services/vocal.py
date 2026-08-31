"""Vocal role helpers: weight normalization and ensemble take allocation.

Raw ``weight_percent`` values are stored as entered. Normalization to 100% and
the mapping to an integer number of ensemble takes are computed on read, so the
UI can show "Brian 70 / Pete 20 / Brad 10  ->  7 / 2 / 1 takes" without ever
mutating what the user typed.
"""

from __future__ import annotations

from sr.common.allocation import largest_remainder_allocation, normalize_weights
from sr.models.vocal import VocalRole
from sr.schemas.vocal import NormalizedShare


def normalized_shares(role: VocalRole) -> list[NormalizedShare]:
    if not role.assignments:
        return []
    weights = {a.singer_id: a.weight_percent for a in role.assignments}
    norm = normalize_weights(weights)
    # Ensemble roles distribute takes; solo roles (lead/double) are 1 take each.
    size = role.ensemble_size if role.role_type in ("background", "gang", "harmony") else 1
    alloc = largest_remainder_allocation(
        weights, size, tie_break_order=sorted(weights)
    ).counts
    return [
        NormalizedShare(
            singer_id=a.singer_id,
            weight_percent=a.weight_percent,
            normalized_percent=norm[a.singer_id],
            ensemble_takes=alloc.get(a.singer_id, 0),
        )
        for a in role.assignments
    ]
