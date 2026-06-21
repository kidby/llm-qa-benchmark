"""Hidden test: fails on the buggy even-length branch, passes once fixed."""

from __future__ import annotations

from median import median


def test_even_length_averages_middle() -> None:
    assert median([1, 2, 3, 4]) == 2.5
    assert median([10, 20]) == 15.0


def test_odd_length() -> None:
    assert median([3, 1, 2]) == 2


def test_empty_raises() -> None:
    import pytest

    with pytest.raises(ValueError):
        median([])
