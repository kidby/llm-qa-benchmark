"""Hidden test: fails on the buggy version, passes once the loop bound is fixed."""

from __future__ import annotations

from binary_search import binary_search


def test_finds_every_element() -> None:
    items = [1, 3, 5, 7, 9, 11]
    for i, value in enumerate(items):
        assert binary_search(items, value) == i


def test_finds_last_and_single() -> None:
    assert binary_search([2, 4, 6], 6) == 2
    assert binary_search([42], 42) == 0


def test_absent_returns_minus_one() -> None:
    assert binary_search([1, 2, 3], 4) == -1
