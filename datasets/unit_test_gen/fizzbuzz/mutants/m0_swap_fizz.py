"""Mutant: returns "Buzz" where it should return "Fizz" (3 vs 5 swapped)."""

from __future__ import annotations


def fizzbuzz(n: int) -> str:
    """Buggy variant: 3 returns Buzz instead of Fizz."""
    if not isinstance(n, int) or isinstance(n, bool):
        raise ValueError("n must be an integer")
    if n <= 0:
        raise ValueError("n must be positive")
    if n % 15 == 0:
        return "FizzBuzz"
    if n % 3 == 0:
        return "Buzz"
    if n % 5 == 0:
        return "Fizz"
    return str(n)
