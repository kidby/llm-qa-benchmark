"""The metric registry — data-driven roll-ups over per-sample score rows.

Adding a metric is adding one entry to ``METRICS``: a function from a per-(model,
track) DataFrame to a float. Every entry automatically becomes a ``summary.csv``
column, a row in ``report.md``, and a series on the dashboard — no other code
changes. Metrics gracefully return ``nan`` when their inputs are absent for a track.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

from qabench.types import Metric


def _rate(numerator: pd.Series, denominator: pd.Series) -> float:
    num = pd.to_numeric(numerator, errors="coerce").sum()
    den = pd.to_numeric(denominator, errors="coerce").sum()
    return float(num / den) if den else float("nan")


def _mean(df: pd.DataFrame, col: str) -> float:
    if col not in df:
        return float("nan")
    series = pd.to_numeric(df[col], errors="coerce")
    return float(series.mean()) if series.notna().any() else float("nan")


def _bool_mean(df: pd.DataFrame, col: str) -> float:
    if col not in df:
        return float("nan")
    # Rows where the field is absent (NaN — a track that doesn't emit this column)
    # are excluded, not counted as False/True.
    series = df[col].map(_to_bool).dropna()
    return float(series.mean()) if len(series) else float("nan")


def _to_bool(value: object) -> float:
    # JSONL preserves types, so values arrive as real bools, numbers, or None/NaN.
    # Missing values (a field a track does not emit) are excluded by _bool_mean.
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return float("nan")
    if isinstance(value, bool | int | float):
        return 1.0 if value else 0.0
    return float("nan")


# --- individual metrics -----------------------------------------------------


def cost_per_run(df: pd.DataFrame) -> float:
    """Average dollar cost per sample."""
    if "cost" not in df or df["sample_id"].nunique() == 0:
        return float("nan")
    return float(pd.to_numeric(df["cost"], errors="coerce").sum() / df["sample_id"].nunique())


def tok_per_s(df: pd.DataFrame) -> float:
    """Output tokens per second of latency."""
    if "tokens_out" not in df or "latency_s" not in df:
        return float("nan")
    return _rate(df["tokens_out"], df["latency_s"])


def mean_latency_s(df: pd.DataFrame) -> float:
    """Mean wall-clock latency per sample, in seconds."""
    return _mean(df, "latency_s")


def output_tokens(df: pd.DataFrame) -> float:
    """Mean output tokens per sample; a proxy for verbosity and cost."""
    return _mean(df, "tokens_out")


def cost_per_correct(df: pd.DataFrame) -> float:
    """Dollars spent per passing sample; the cost of a correct result.

    NaN when nothing passed, since the cost bought no correct output.
    """
    if "cost" not in df or "passed" not in df:
        return float("nan")
    n_correct = df["passed"].map(_to_bool).fillna(0.0).sum()
    if n_correct == 0:
        return float("nan")
    return float(pd.to_numeric(df["cost"], errors="coerce").sum() / n_correct)


def false_positive_rate(df: pd.DataFrame) -> float:
    """Unit-test track: fraction of tests that fail on the correct implementation."""
    if "tests_failing_on_correct" not in df or "tests_total" not in df:
        return float("nan")
    return _rate(df["tests_failing_on_correct"], df["tests_total"])


def false_negative_rate(df: pd.DataFrame) -> float:
    """Unit-test track: fraction of injected bugs (mutants) the suite misses."""
    if "mutants_surviving" not in df or "mutants_total" not in df:
        return float("nan")
    return _rate(df["mutants_surviving"], df["mutants_total"])


def recall(df: pd.DataFrame) -> float:
    """Bug-catching recall = mutation-kill rate = 1 - false-negative rate."""
    fn = false_negative_rate(df)
    return float("nan") if np.isnan(fn) else 1.0 - fn


def precision(df: pd.DataFrame) -> float:
    """Bug-catching precision: killed mutants / (killed mutants + false-alarm tests)."""
    if "mutants_killed" not in df or "tests_failing_on_correct" not in df:
        return float("nan")
    tp = pd.to_numeric(df["mutants_killed"], errors="coerce").sum()
    fp = pd.to_numeric(df["tests_failing_on_correct"], errors="coerce").sum()
    return float(tp / (tp + fp)) if (tp + fp) else float("nan")


def f1(df: pd.DataFrame) -> float:
    """Harmonic mean of bug-catching precision and recall."""
    p, r = precision(df), recall(df)
    if np.isnan(p) or np.isnan(r) or (p + r) == 0:
        return float("nan")
    return float(2 * p * r / (p + r))


def code_correctness(df: pd.DataFrame) -> float:
    """Fraction of outputs that execute and are valid (run+pass / repair / e2e)."""
    for col in ("runs_and_valid", "e2e_ran", "repair_passed"):
        if col in df:
            return _bool_mean(df, col)
    return float("nan")


def coverage(df: pd.DataFrame) -> float:
    """Mean line+branch coverage percentage (unit-test track)."""
    return _mean(df, "coverage_pct")


def design_score(df: pd.DataFrame) -> float:
    """Mean judge design/quality score (0..1)."""
    return _mean(df, "design_judge")


def hallucination_rate(df: pd.DataFrame) -> float:
    """Fraction of outputs that reference non-existent APIs."""
    return _bool_mean(df, "hallucinated")


def localization_accuracy(df: pd.DataFrame) -> float:
    """Bug-localization: fraction of exact fault-line hits."""
    return _bool_mean(df, "localized")


def pattern_adoption(df: pd.DataFrame) -> float:
    """e2e_advanced: mean credit for applying the implicitly-required technique.

    ``pattern_used`` is graded (1.0 full / 0.5 partial / 0.0 none), so this is a
    mean rather than a boolean rate — partial credit counts as a half.
    """
    return _mean(df, "pattern_used")


def locator_quality(df: pd.DataFrame) -> float:
    """e2e: mean locator-strategy quality (getByRole > … > css > xpath)."""
    return _mean(df, "locator_quality")


def assertion_quality(df: pd.DataFrame) -> float:
    """e2e: fraction of assertions that are web-first/auto-retrying vs manual."""
    return _mean(df, "assertion_quality")


def waiting_quality(df: pd.DataFrame) -> float:
    """e2e: quality of waiting (web-first/event-based vs arbitrary timeouts)."""
    return _mean(df, "waiting_quality")


def craft_score(df: pd.DataFrame) -> float:
    """Validated static craft signal: mean of the available craft facets.

    Combines positive facets (locator/assertion/waiting/teardown quality) with the
    inverse of the smell rates (hardcoded URLs, DOM-reaching code smells). These
    detectors agreed 10/10 with human labels on the golden set, so this is trusted.
    """
    parts: list[float] = []
    for col in ("locator_quality", "assertion_quality", "waiting_quality", "teardown_hygiene"):
        v = _mean(df, col)
        if not np.isnan(v):
            parts.append(v)
    for col in ("uses_hardcoded_url", "has_code_smell"):
        rate = _bool_mean(df, col)
        if not np.isnan(rate):
            parts.append(1.0 - rate)
    return float(sum(parts) / len(parts)) if parts else float("nan")


def dry_score(df: pd.DataFrame) -> float:
    """e2e: 1.0 = no duplicated setup/action statements; lower = more copy-paste.

    Report-only for now: not yet folded into the composite, pending validation
    against the human golden set (same bar the other static signals cleared).
    """
    return _mean(df, "dry_score")


def review_score(df: pd.DataFrame) -> float:
    """LLM review judge's mean craft opinion (0..1).

    An opinionated signal: it correlated only weakly with human craft labels on the
    golden set (Spearman ~0.45), so it enters the composite at a LOW weight and never
    overrides the execution-based and validated-static signals.
    """
    return _mean(df, "review_score")


def one_shot_pass_rate(df: pd.DataFrame) -> float:
    """Fraction of samples solved on the very first attempt."""
    if "passed" not in df or "attempts" not in df:
        return float("nan")
    passed = df["passed"].map(_to_bool)
    first = pd.to_numeric(df["attempts"], errors="coerce") == 1
    return float((passed * first).mean())


def multi_shot_pass_rate(df: pd.DataFrame) -> float:
    """Fraction of samples solved within the allowed number of attempts."""
    return _bool_mean(df, "passed")


def composite(df: pd.DataFrame) -> float:
    """A 0..1 headline score; per-track weighting of the available signals."""
    parts: list[tuple[float, float]] = []  # (value, weight)

    def add(value: float, weight: float) -> None:
        if not np.isnan(value):
            parts.append((value, weight))

    add(recall(df), 3.0)  # mutation kill dominates the unit-test track
    add(multi_shot_pass_rate(df), 2.0)
    add(coverage(df) / 100.0 if not np.isnan(coverage(df)) else float("nan"), 1.0)
    add(design_score(df), 1.0)
    add(localization_accuracy(df), 2.0)
    add(pattern_adoption(df), 2.0)  # implicit-technique recognition (e2e_advanced)
    add(craft_score(df), 1.0)  # validated static craft (locators/assertions/waiting/smells)
    add(review_score(df), 0.5)  # opinionated LLM review — low weight (weak human corr)
    if not np.isnan(hallucination_rate(df)):
        add(1.0 - hallucination_rate(df), 1.0)
    if not parts:
        return float("nan")
    total_w = sum(w for _, w in parts)
    return float(sum(v * w for v, w in parts) / total_w)


METRICS: dict[str, Metric] = {
    "composite": composite,
    "multi_shot_pass_rate": multi_shot_pass_rate,
    "one_shot_pass_rate": one_shot_pass_rate,
    "code_correctness": code_correctness,
    "recall": recall,
    "precision": precision,
    "f1": f1,
    "false_positive_rate": false_positive_rate,
    "false_negative_rate": false_negative_rate,
    "coverage": coverage,
    "design_score": design_score,
    "localization_accuracy": localization_accuracy,
    "pattern_adoption": pattern_adoption,
    "craft_score": craft_score,
    "locator_quality": locator_quality,
    "assertion_quality": assertion_quality,
    "waiting_quality": waiting_quality,
    "dry_score": dry_score,
    "review_score": review_score,
    "hallucination_rate": hallucination_rate,
    "cost_per_run": cost_per_run,
    "cost_per_correct": cost_per_correct,
    "tok_per_s": tok_per_s,
    "mean_latency_s": mean_latency_s,
    "output_tokens": output_tokens,
}


def tier(composite_score: float) -> str:
    """Map a composite score to an A/B/C tier (akitaonrails-style)."""
    if np.isnan(composite_score):
        return "n/a"
    if composite_score >= 0.80:
        return "A"
    if composite_score >= 0.60:
        return "B"
    return "C"
