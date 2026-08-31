"""Blueprint acceptance tests 18-19: percentage normalization + largest-remainder."""

from __future__ import annotations

import pytest

from sr.common.allocation import largest_remainder_allocation, normalize_weights
from sr.common.seeds import bounded_jitter, derive_seed


def test_normalize_basic():
    assert normalize_weights({"a": 70, "b": 20, "c": 10}) == {"a": 70.0, "b": 20.0, "c": 10.0}


def test_normalize_scales_to_100():
    out = normalize_weights({"a": 7, "b": 2, "c": 1})
    assert sum(out.values()) == pytest.approx(100.0)


def test_normalize_all_zero_is_equal_split():
    assert normalize_weights({"a": 0, "b": 0}) == {"a": 50.0, "b": 50.0}


def test_canonical_702010_over_10():
    alloc = largest_remainder_allocation({"brian": 70, "pete": 20, "brad": 10}, 10)
    assert alloc.counts == {"brian": 7, "pete": 2, "brad": 1}
    assert sum(alloc.counts.values()) == 10


@pytest.mark.parametrize("size", [1, 3, 4, 5, 8, 16, 32])
def test_allocation_always_sums_to_ensemble_size(size):
    alloc = largest_remainder_allocation({"a": 33, "b": 33, "c": 34}, size)
    assert sum(alloc.counts.values()) == size


def test_allocation_is_deterministic_and_tie_stable():
    w = {"x": 50, "y": 50}
    a = largest_remainder_allocation(w, 3, tie_break_order=["x", "y"])
    b = largest_remainder_allocation(w, 3, tie_break_order=["x", "y"])
    assert a.counts == b.counts == {"x": 2, "y": 1}


def test_as_takes_flattens_in_stable_order():
    alloc = largest_remainder_allocation({"brian": 70, "pete": 20, "brad": 10}, 10)
    takes = alloc.as_takes()
    assert takes.count("brian") == 7
    assert takes == sorted(takes)  # grouped, stable


def test_derive_seed_stable_and_distinct():
    assert derive_seed(1337, "voice", "brian", 0) == derive_seed(1337, "voice", "brian", 0)
    assert derive_seed(1337, "voice", "brian", 0) != derive_seed(1337, "voice", "brian", 1)
    assert derive_seed(1337, "voice", "brian", 0) != derive_seed(9, "voice", "brian", 0)


def test_bounded_jitter_within_range():
    for i in range(200):
        v = bounded_jitter(derive_seed(1, i), -20, 20)
        assert -20 <= v <= 20
