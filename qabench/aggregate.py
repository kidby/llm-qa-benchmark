"""Aggregate per-sample scores into a per-(model, track) metric summary.

Per-track metrics are pooled over all (sample x trial) rows — so running multiple
trials and averaging happens for free. The headline ``track="ALL"`` composite is
the equal-weight mean of the per-track composites over the execution-grounded
(``HEADLINE_TRACKS``) tracks, so each track counts once regardless of how many
samples it has and the judge-only ``test_case_design`` track is excluded. We also
report ``n_trials`` and the run-to-run spread of the headline score
(``composite_std``).
"""

from __future__ import annotations

import math
from collections.abc import Callable

import pandas as pd

from qabench.scoring.metrics import METRICS, composite, tier
from qabench.tracks import HEADLINE_TRACKS


def summarize(scored: pd.DataFrame) -> pd.DataFrame:
    """Apply every registered metric per (model, track) and per model overall.

    Returns one row per ``(model_slug, track)`` plus a ``track="ALL"`` rollup row
    per model, each carrying every metric column, ``n_trials``/``composite_std``,
    and an A/B/C ``tier``.
    """
    if scored.empty:
        return pd.DataFrame()

    rows: list[dict[str, object]] = []
    for (model, track), group in scored.groupby(["model_slug", "track"], sort=True):
        rows.append(_metric_row(str(model), str(track), group))
    for model, group in scored.groupby("model_slug", sort=True):
        rows.append(_overall_row(str(model), group))

    summary = pd.DataFrame(rows)
    return summary.sort_values(["track", "composite"], ascending=[True, False]).reset_index(
        drop=True
    )


def _headline_composite(group: pd.DataFrame) -> float:
    """Equal-weight mean of per-track composites over the headline tracks present."""
    vals = [
        composite(track_group)
        for track, track_group in group.groupby("track")
        if str(track) in HEADLINE_TRACKS
    ]
    vals = [v for v in vals if not math.isnan(v)]
    return float(sum(vals) / len(vals)) if vals else float("nan")


def _composite_std(group: pd.DataFrame) -> tuple[int, float]:
    """Return ``(n_trials, std of the per-trial composite)`` for a single track."""
    return _trial_spread(group, composite)


def _headline_composite_std(group: pd.DataFrame) -> tuple[int, float]:
    """``(n_trials, std)`` of the per-trial headline (per-track-averaged) composite."""
    return _trial_spread(group, _headline_composite)


def _trial_spread(group: pd.DataFrame, fn: Callable[[pd.DataFrame], float]) -> tuple[int, float]:
    if "trial" not in group:
        return 1, float("nan")
    per_trial = [fn(g) for _, g in group.groupby("trial")]
    per_trial = [v for v in per_trial if not math.isnan(v)]
    n = len(per_trial)
    if n < 2:
        return max(n, 1), float("nan")
    mean = sum(per_trial) / n
    var = sum((v - mean) ** 2 for v in per_trial) / (n - 1)  # sample std
    return n, math.sqrt(var)


def _metric_row(model: str, track: str, group: pd.DataFrame) -> dict[str, object]:
    n_trials, comp_std = _composite_std(group)
    row: dict[str, object] = {
        "model_slug": model,
        "track": track,
        "n_samples": int(group["sample_id"].nunique()),
        "n_trials": n_trials,
    }
    for name, fn in METRICS.items():
        row[name] = round(fn(group), 4)
    row["composite_std"] = round(comp_std, 4) if not math.isnan(comp_std) else float("nan")
    composite_val = row.get("composite")
    row["tier"] = tier(float(composite_val)) if isinstance(composite_val, float) else "n/a"
    return row


def _overall_row(model: str, group: pd.DataFrame) -> dict[str, object]:
    """The ``ALL`` rollup: pooled informational metrics, headline-averaged composite."""
    row = _metric_row(model, "ALL", group)
    comp = _headline_composite(group)
    n_trials, comp_std = _headline_composite_std(group)
    row["n_trials"] = n_trials
    row["composite"] = round(comp, 4) if not math.isnan(comp) else float("nan")
    row["composite_std"] = round(comp_std, 4) if not math.isnan(comp_std) else float("nan")
    row["tier"] = tier(comp)
    return row
