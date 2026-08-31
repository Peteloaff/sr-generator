"""The micro-variation engine.

Turns a VocalRole (+ its weighted assignments) and a parent seed into a
deterministic list of ``TakeSpec`` - one per virtual performance - with every
applied timing / pitch / formant / gain / pan value fixed up front. Pure and
unit-tested; the render step just executes these specs.
"""

from __future__ import annotations

from dataclasses import dataclass

from sr.common.allocation import largest_remainder_allocation
from sr.common.seeds import bounded_jitter, derive_seed
from sr.models.vocal import VocalRole

ENSEMBLE_ROLES = {"background", "gang", "harmony"}


@dataclass(frozen=True)
class TakeSpec:
    role_id: str
    role_type: str
    singer_id: str
    take_index: int
    child_seed: int
    timing_offset_ms: float
    pitch_cents: float
    formant_shift: float
    gain_db: float
    pan: float


def _round(v: float, n: int = 3) -> float:
    return round(float(v), n)


def plan_role_takes(
    role: VocalRole, parent_seed: int, *, flat: bool = False
) -> list[TakeSpec]:
    """Plan the takes for a role.

    ``flat=True`` is the A/B baseline - a naive "same take, N copies" stack: no
    humanisation, no stereo spread, no interval-independent detune. Musical
    intervals (harmony/octave) are kept even in flat mode; they are the
    arrangement, not the production.
    """
    if not role.assignments:
        return []

    weights = {a.singer_id: a.weight_percent for a in role.assignments}
    fixed = {a.singer_id: a for a in role.assignments}
    ensemble = role.ensemble_size if role.role_type in ENSEMBLE_ROLES else 1

    alloc = largest_remainder_allocation(
        weights, ensemble, tie_break_order=sorted(weights)
    ).counts

    take_order: list[str] = []
    for singer_id in sorted(alloc):
        take_order.extend([singer_id] * alloc[singer_id])
    total = len(take_order)

    specs: list[TakeSpec] = []
    per_singer_idx: dict[str, int] = {}
    for global_idx, singer_id in enumerate(take_order):
        k = per_singer_idx.get(singer_id, 0)
        per_singer_idx[singer_id] = k + 1
        a = fixed[singer_id]

        base = derive_seed(parent_seed, role.id, singer_id, k)
        if flat:
            jt = jp = jf = spread = 0.0
        else:
            ht, hp, hf = (
                role.humanize_timing_ms, role.humanize_pitch_cents, role.humanize_formant
            )
            jt = bounded_jitter(derive_seed(base, "timing"), -ht, ht)
            jp = bounded_jitter(derive_seed(base, "pitch"), -hp, hp)
            jf = bounded_jitter(derive_seed(base, "formant"), -hf, hf)
            # Deterministic stereo spread: takes fan out across +/- role.width.
            if total > 1 and role.width > 0:
                pos = (global_idx / (total - 1)) - 0.5  # -0.5 .. 0.5
                spread = pos * 2.0 * role.width
                spread += bounded_jitter(
                    derive_seed(base, "pan"), -role.width * 0.1, role.width * 0.1
                )
            else:
                spread = 0.0

        interval = getattr(a, "interval_semitones", 0.0) or 0.0
        specs.append(
            TakeSpec(
                role_id=role.id,
                role_type=role.role_type,
                singer_id=singer_id,
                take_index=k,
                child_seed=base,
                timing_offset_ms=_round(a.timing_offset_ms + jt),
                pitch_cents=_round((interval + a.pitch_offset_semitones) * 100.0 + jp),
                formant_shift=_round(a.formant_shift + jf),
                gain_db=_round(a.gain_db),
                pan=_round(max(-100.0, min(100.0, a.pan + spread))),
            )
        )
    return specs
