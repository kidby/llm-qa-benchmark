"""Mutant: drops the positivity check entirely (no ValueError for n <= 0)."""

from __future__ import annotations


def fizzbuzz(n: int) -> str:
    """Buggy variant: missing positivity validation."""
    if not isinstance(n, int) or isinstance(n, bool):
        raise ValueError("n must be an integer")
    if n % 15 == 0:
        return "FizzBuzz"
    if n % 3 == 0:
        return "Fizz"
    if n % 5 == 0:
        return "Buzz"
    return str(n)
