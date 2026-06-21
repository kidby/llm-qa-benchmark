"""Mutant: accepts percent > 100 (upper-bound validation removed)."""

from __future__ import annotations


def apply_discount(price: float, percent: float) -> float:
    """Buggy variant: only checks the lower bound on percent."""
    if price < 0:
        raise ValueError("price must be non-negative")
    if percent < 0:
        raise ValueError("percent must be between 0 and 100")
    discounted = price * (1 - percent / 100)
    return round(discounted, 2)
