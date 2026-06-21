"""Mutant: increases the price instead of discounting it."""

from __future__ import annotations


def apply_discount(price: float, percent: float) -> float:
    """Buggy variant: ``1 + percent`` instead of ``1 - percent``."""
    if price < 0:
        raise ValueError("price must be non-negative")
    if percent < 0 or percent > 100:
        raise ValueError("percent must be between 0 and 100")
    discounted = price * (1 + percent / 100)
    return round(discounted, 2)
