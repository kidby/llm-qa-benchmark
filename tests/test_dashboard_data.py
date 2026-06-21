"""Tests for the dashboard's pure data/figure helpers (no Reflex runtime)."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import pytest

# The dashboard app lives under dashboard/ (its own Reflex project), not in the
# installed package — put it on the path so we can unit-test its data layer.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "dashboard"))

data = pytest.importorskip("qabench_dash.data")


def _summary() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "model_slug": "m1",
                "track": "ALL",
                "composite": 0.9,
                "tier": "A",
                "cost_per_run": 0.5,
                "one_shot_pass_rate": 0.6,
                "multi_shot_pass_rate": 0.9,
                "code_correctness": 1.0,
                "recall": 0.9,
                "false_positive_rate": 0.0,
                "false_negative_rate": 0.1,
                "coverage": 95.0,
                "design_score": 0.8,
                "hallucination_rate": 0.0,
                "tok_per_s": 40.0,
            },
            {
                "model_slug": "m1",
                "track": "unit_test_gen",
                "composite": 0.9,
                "tier": "A",
                "cost_per_run": 0.5,
                "one_shot_pass_rate": 0.6,
                "multi_shot_pass_rate": 0.9,
                "code_correctness": 1.0,
                "recall": 0.9,
                "false_positive_rate": 0.0,
                "false_negative_rate": 0.1,
                "coverage": 95.0,
                "design_score": 0.8,
                "hallucination_rate": 0.0,
                "tok_per_s": 40.0,
            },
        ]
    )


def test_all_figures_build() -> None:
    s = _summary()
    for fig in (
        data.leaderboard_fig(s),
        data.cost_quality_fig(s),
        data.oneshot_fig(s),
        data.track_heatmap_fig(s),
        data.metric_bar_fig(s, "recall"),
        data.category_bars_fig(s),
        data.per_track_bars_fig(s),
    ):
        assert isinstance(fig, go.Figure)


def test_pattern_matrix_builds_from_scored() -> None:
    scored = pd.DataFrame(
        [
            {
                "model_slug": "m1",
                "track": "e2e_advanced",
                "uses_page_object": True,
                "uses_fixtures": False,
                "uses_polling": False,
                "uses_network": True,
                "uses_api": True,
            },
            {
                "model_slug": "m2",
                "track": "e2e_advanced",
                "uses_page_object": False,
                "uses_fixtures": False,
                "uses_polling": True,
                "uses_network": False,
                "uses_api": True,
            },
        ]
    )
    assert isinstance(data.pattern_matrix_fig(scored), go.Figure)
    assert isinstance(data.pattern_matrix_fig(pd.DataFrame()), go.Figure)


def test_figures_handle_empty() -> None:
    empty = pd.DataFrame()
    assert isinstance(data.leaderboard_fig(empty), go.Figure)
    assert isinstance(data.track_heatmap_fig(empty), go.Figure)


def test_scorecard_rows_formatted() -> None:
    rows = data.scorecard_rows(_summary())
    assert rows[0]["model"] == "m1"
    assert rows[0]["tier"] == "A"
    assert rows[0]["composite"] == "0.9"


def test_available_metrics_matches_registry() -> None:
    from qabench.scoring.metrics import METRICS

    assert data.available_metrics() == list(METRICS)


def test_latest_per_model_keeps_newest_per_model(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Two runs: 'old' has model a, 'new' has a (updated) and b. The comparison
    # should keep b plus a's newest row, one row per model per track.
    results = tmp_path / "results"
    for run, rows in {
        "old": [{"model_slug": "a", "track": "ALL", "composite": 0.5, "tier": "C"}],
        "new": [
            {"model_slug": "a", "track": "ALL", "composite": 0.9, "tier": "A"},
            {"model_slug": "b", "track": "ALL", "composite": 0.7, "tier": "B"},
        ],
    }.items():
        d = results / run
        d.mkdir(parents=True)
        pd.DataFrame(rows).to_csv(d / "summary.csv", index=False)
    # Make 'new' newer than 'old'.
    import os

    os.utime(results / "old" / "summary.csv", (1, 1))
    os.utime(results / "new" / "summary.csv", (2, 2))
    monkeypatch.setattr(data, "RESULTS_DIR", results)

    combined = data.latest_per_model()
    by_model = combined.set_index("model_slug")["composite"].to_dict()
    assert by_model == {"a": 0.9, "b": 0.7}  # a's newer 0.9, not the stale 0.5
