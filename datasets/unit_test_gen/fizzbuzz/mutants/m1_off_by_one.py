"""Mutant: boundary off-by-one, treats n <= 0 incorrectly (allows 0)."""

from __future__ import annotations


def fizzbuzz(n: int) -> str:
    """Buggy variant: rejects n < 0 instead of n <= 0, so 0 slips through."""
    if not isinstance(n, int) or isinstance(n, bool):
        raise ValueError("n must be an integer")
    if n < 0:
        raise ValueError("n must be positive")
    if n % 15 == 0:
        return "FizzBuzz"
    if n % 3 == 0:
        return "Fizz"
    if n % 5 == 0:
        return "Buzz"
    return str(n)
