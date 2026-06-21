"""FizzBuzz with input validation."""

from __future__ import annotations


def fizzbuzz(n: int) -> str:
    """Return the FizzBuzz string for a positive integer ``n``.

    - multiples of 15 -> "FizzBuzz"
    - multiples of 3  -> "Fizz"
    - multiples of 5  -> "Buzz"
    - otherwise the number as a string

    Raises:
        ValueError: if ``n`` is not a positive integer.
    """
    if not isinstance(n, int) or isinstance(n, bool):
        raise ValueError("n must be an integer")
    if n <= 0:
        raise ValueError("n must be positive")
    if n % 15 == 0:
        return "FizzBuzz"
    if n % 3 == 0:
        return "Fizz"
    if n % 5 == 0:
        return "Buzz"
    return str(n)
