"""Stage 2: the micro-variation engine - deterministic take plans."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from sr.services.layering import plan_role_takes


def _assign(singer_id, weight, **over):
    base = dict(
        singer_id=singer_id, weight_percent=weight, timing_offset_ms=0.0,
        pitch_offset_semitones=0.0, formant_shift=0.0, gain_db=0.0, pan=0.0,
    )
    base.update(over)
    return SimpleNamespace(**base)


def _role(role_type, assignments, *, ensemble_size=1, width=0.0, ht=0.0, hp=0.0, hf=0.0):
    return SimpleNamespace(
        id="role-1", role_type=role_type, ensemble_size=ensemble_size, width=width,
        humanize_timing_ms=ht, humanize_pitch_cents=hp, humanize_formant=hf,
        assignments=assignments,
    )


def test_background_702010_at_10_gives_7_2_1_take_specs():
    role = _role(
        "background",
        [_assign("brian", 70), _assign("pete", 20), _assign("brad", 10)],
        ensemble_size=10,
    )
    specs = plan_role_takes(role, parent_seed=99)
    counts = {}
    for s in specs:
        counts[s.singer_id] = counts.get(s.singer_id, 0) + 1
    assert counts == {"brian": 7, "pete": 2, "brad": 1}
    assert [s.take_index for s in specs if s.singer_id == "brian"] == [0, 1, 2, 3, 4, 5, 6]


def test_lead_is_one_take_regardless_of_ensemble_size():
    role = _role("lead", [_assign("brian", 100)], ensemble_size=8)
    assert len(plan_role_takes(role, 1)) == 1


def test_plan_is_deterministic():
    role = _role(
        "gang", [_assign("a", 50), _assign("b", 50)], ensemble_size=6, width=80, ht=20, hp=10
    )
    a = plan_role_takes(role, 42)
    b = plan_role_takes(role, 42)
    assert [vars(x) for x in a] == [vars(x) for x in b]
    assert [vars(x) for x in plan_role_takes(role, 43)] != [vars(x) for x in a]


def test_humanization_stays_within_bounds():
    role = _role(
        "background", [_assign("a", 100)], ensemble_size=12, width=100, ht=25, hp=12, hf=30
    )
    for s in plan_role_takes(role, 7):
        assert abs(s.timing_offset_ms) <= 25 + 1e-6
        assert abs(s.pitch_cents) <= 12 + 1e-6
        assert abs(s.formant_shift) <= 30 + 1e-6
        assert -100 <= s.pan <= 100


def test_fixed_per_assignment_offsets_are_added():
    role = _role(
        "double",
        [_assign("pete", 100, pitch_offset_semitones=-1.0, gain_db=-3.0, pan=-20.0)],
    )
    (spec,) = plan_role_takes(role, 5)
    assert spec.pitch_cents == pytest.approx(-100.0)  # -1 semitone, no jitter
    assert spec.gain_db == -3.0
    assert spec.pan == -20.0


def test_no_assignments_no_takes():
    assert plan_role_takes(_role("lead", []), 1) == []
