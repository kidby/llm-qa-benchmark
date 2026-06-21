"""Mutant: forgets to round, leaking floating-point noise."""

from __future__ import annotations


def apply_discount(price: float, percent: float) -> float:
    """Buggy variant: returns the unrounded value."""
    if price < 0:
        raise ValueError("price must be non-negative")
    if percent < 0 or percent > 100:
        raise ValueError("percent must be between 0 and 100")
    discounted = price * (1 - percent / 100)
    return discounted
