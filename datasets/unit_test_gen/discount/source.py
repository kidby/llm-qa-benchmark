"""Apply a percentage discount to a price."""

from __future__ import annotations


def apply_discount(price: float, percent: float) -> float:
    """Return ``price`` reduced by ``percent``%, rounded to 2 decimals.

    Args:
        price: A non-negative price.
        percent: A discount percentage in the closed range [0, 100].

    Raises:
        ValueError: if ``price`` is negative or ``percent`` is outside [0, 100].
    """
    if price < 0:
        raise ValueError("price must be non-negative")
    if percent < 0 or percent > 100:
        raise ValueError("percent must be between 0 and 100")
    discounted = price * (1 - percent / 100)
    return round(discounted, 2)
