"""Objective scoring for the bug-localization track.

Localization accuracy: did the model name a line span covering the known fault
set (exact, or within a +/-1 line tolerance)? Optional repair execution: apply
the model's fix over its predicted span and run the hidden test — does it pass?
"""

from __future__ import annotations

from typing import Any

from qabench.sandbox import PYTHON_IMAGE
from qabench.types import Sample, ScoreContext, ScoreRow


def _as_int(raw: Any) -> int | None:
    if isinstance(raw, bool):  # bool is an int subclass — exclude it
        return None
    if isinstance(raw, int):
        return raw
    if isinstance(raw, str) and raw.strip().isdigit():
        return int(raw.strip())
    return None


def _predicted_span(parsed: Any) -> tuple[int, int] | None:
    """The predicted buggy line range.

    Accepts the current ``start_line``/``end_line`` shape and falls back to the
    legacy single ``line`` field so previously collected responses score
    identically. Returns ``(start, end)`` with ``start <= end``, or ``None``.
    """
    if not isinstance(parsed, dict):
        return None
    start = _as_int(parsed.get("start_line"))
    end = _as_int(parsed.get("end_line"))
    if start is None and end is None:
        legacy = _as_int(parsed.get("line"))
        if legacy is None:
            return None
        return legacy, legacy
    if start is None:
        start = end
    if end is None:
        end = start
    assert start is not None and end is not None
    return (start, end) if start <= end else (end, start)


def score_localization(sample: Sample, parsed: Any, ctx: ScoreContext) -> ScoreRow:
    """Score the predicted fault span and (when a hidden test exists) the repair."""
    fault_lines = [int(x) for x in sample.payload.get("fault_lines", [])]
    span = _predicted_span(parsed)
    if span is None or not fault_lines:
        exact = near = False
    else:
        start, end = span
        # Localized when every known fault line falls inside the predicted span;
        # the +/-1 tolerance widens the span by one line on each side.
        exact = all(start <= f <= end for f in fault_lines)
        near = all(start - 1 <= f <= end + 1 for f in fault_lines)

    row: ScoreRow = {
        "predicted_line": span[0] if span is not None else -1,
        "predicted_end_line": span[1] if span is not None else -1,
        "localized": exact,
        "localized_within_1": near,
        "passed": exact,
    }

    repair = _try_repair(sample, parsed, span, ctx)
    if repair is not None:
        row["repair_attempted"] = True
        row["repair_passed"] = repair
        # A working repair is a stronger signal than line matching alone.
        row["passed"] = bool(near and repair) or exact
    else:
        row["repair_attempted"] = False
        row["repair_passed"] = False
    return row


def _try_repair(
    sample: Sample, parsed: Any, span: tuple[int, int] | None, ctx: ScoreContext
) -> bool | None:
    test = sample.payload.get("test")
    module_name = sample.payload.get("module_name")
    fix = parsed.get("proposed_fix") if isinstance(parsed, dict) else None
    if not test or not module_name or span is None or not isinstance(fix, str):
        return None

    start, end = span
    source_lines = str(sample.payload.get("source", "")).splitlines()
    if not (1 <= start <= end <= len(source_lines)):
        return None

    patched = list(source_lines)
    fix_lines = fix.splitlines() or [fix]
    # Re-indent a single-line fix to match the replaced line; for a multi-line
    # block trust the indentation the model supplied.
    if start == end and len(fix_lines) == 1 and not fix_lines[0].startswith((" ", "\t")):
        original = source_lines[start - 1]
        indent = original[: len(original) - len(original.lstrip())]
        fix_lines = [indent + fix_lines[0].strip()]
    patched[start - 1 : end] = fix_lines

    res = ctx.sandbox.run(
        image=PYTHON_IMAGE,
        files={
            f"{module_name}.py": "\n".join(patched) + "\n",
            "test_hidden.py": str(test),
        },
        command=["python", "-m", "pytest", "test_hidden.py", "-q", "-p", "no:cacheprovider"],
        timeout_s=60,
    )
    return res.exit_code == 0
