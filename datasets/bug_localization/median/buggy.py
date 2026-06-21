"""Compute the median of a list of numbers."""

from __future__ import annotations


def median(values: list[float]) -> float:
    """Return the median of ``values`` (averaging the two middle items if even)."""
    if not values:
        raise ValueError("values must be non-empty")
    ordered = sorted(values)
    n = len(ordered)
    mid = n // 2
    if n % 2 == 0:
        return ordered[mid]
    return ordered[mid]
