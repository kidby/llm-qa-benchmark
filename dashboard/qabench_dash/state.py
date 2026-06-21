"""Reflex state — exposes the cross-run model comparison as figures and rows.

The dashboard shows each model's most recent benchmark result (combined across all
runs), so every model that has been evaluated appears in one comparison.
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import reflex as rx

from qabench_dash import data


def _comparison() -> pd.DataFrame:
    """Each model's latest scored summary, combined into one frame."""
    return data.latest_per_model()


def _scored() -> pd.DataFrame:
    """Per-sample scored rows from the newest run (for pattern-level detail)."""
    runs = data.list_runs()
    return data.load_scored(runs[0]) if runs else pd.DataFrame()


class State(rx.State):
    """Dashboard state: the chosen metric drives the metric-explorer chart."""

    metric: str = "composite"

    @rx.var(cache=True)
    def metrics(self) -> list[str]:
        """Every metric name the registry produces."""
        return data.available_metrics()

    @rx.var(cache=True)
    def has_data(self) -> bool:
        """Whether any scored run exists to compare."""
        return not _comparison().empty

    @rx.var(cache=True)
    def scorecard(self) -> list[dict[str, str]]:
        """Per-model overall metrics for the scorecard table."""
        return data.scorecard_rows(_comparison())

    @rx.var(cache=True)
    def leaderboard(self) -> go.Figure:
        """Leaderboard bar figure."""
        return data.leaderboard_fig(_comparison())

    @rx.var(cache=True)
    def cost_quality(self) -> go.Figure:
        """Cost-vs-quality scatter figure."""
        return data.cost_quality_fig(_comparison())

    @rx.var(cache=True)
    def oneshot(self) -> go.Figure:
        """One-shot vs multi-shot grouped-bar figure."""
        return data.oneshot_fig(_comparison())

    @rx.var(cache=True)
    def heatmap(self) -> go.Figure:
        """Model x track composite heatmap figure."""
        return data.track_heatmap_fig(_comparison())

    @rx.var(cache=True)
    def category_bars(self) -> go.Figure:
        """Component vs system composite per model."""
        return data.category_bars_fig(_comparison())

    @rx.var(cache=True)
    def per_track(self) -> go.Figure:
        """Small multiples: composite per track in shared model order."""
        return data.per_track_bars_fig(_comparison())

    @rx.var(cache=True)
    def pattern_matrix(self) -> go.Figure:
        """Advanced-pattern adoption per model (model x technique)."""
        return data.pattern_matrix_fig(_scored())

    @rx.var(cache=True)
    def metric_chart(self) -> go.Figure:
        """Bar of the currently-selected metric across models."""
        return data.metric_bar_fig(_comparison(), self.metric)

    def set_metric(self, value: str) -> None:
        """Select a different metric for the explorer."""
        self.metric = value
