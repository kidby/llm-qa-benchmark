"""Loading + figure construction for the dashboard (pure functions, testable).

Reads the same ``results/<run_id>/`` CSVs the CLI writes. Crucially, charts that
show metrics read whatever columns the metric registry produced, so a newly added
metric appears here automatically.
"""

from __future__ import annotations

import math

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from qabench.config import RESULTS_DIR
from qabench.scoring.metrics import METRICS
from qabench.tracks import CATEGORY_BY_TRACK

from qabench_dash.theme import PALETTE, TIER_COLORS, plotly_layout

# Implicit techniques detected on the e2e_advanced track (see static_checks).
PATTERN_TECHNIQUES = [
    "structure",
    "fixtures",
    "polling",
    "network",
    "api",
    "download",
    "accessibility",
    "performance",
    "realtime",
]

SCORECARD_METRICS = [
    "composite",
    "composite_std",
    "n_trials",
    "code_correctness",
    "recall",
    "false_positive_rate",
    "false_negative_rate",
    "coverage",
    "design_score",
    "pattern_adoption",
    "craft_score",
    "dry_score",
    "review_score",
    "hallucination_rate",
    "one_shot_pass_rate",
    "multi_shot_pass_rate",
    "cost_per_run",
    "cost_per_correct",
    "tok_per_s",
    "mean_latency_s",
    "output_tokens",
]


def list_runs() -> list[str]:
    """Run ids that have a summary, newest first (by file modification time)."""
    if not RESULTS_DIR.is_dir():
        return []
    runs = [d for d in RESULTS_DIR.iterdir() if (d / "summary.csv").exists()]
    runs.sort(key=lambda d: (d / "summary.csv").stat().st_mtime, reverse=True)
    return [d.name for d in runs]


def latest_per_model() -> pd.DataFrame:
    """Combine each model's most recent scored result into one comparison summary.

    Scans every run from newest to oldest and keeps the first (newest) summary rows
    seen for each model, so every model that has ever been benchmarked appears
    exactly once — at its latest result.
    """
    frames: list[pd.DataFrame] = []
    seen: set[str] = set()
    for run_id in list_runs():
        summary = load_summary(run_id)
        if summary.empty:
            continue
        fresh = summary[~summary["model_slug"].isin(seen)]
        if not fresh.empty:
            frames.append(fresh)
            seen.update(fresh["model_slug"].unique())
    if not frames:
        return pd.DataFrame()
    combined = pd.concat(frames, ignore_index=True)
    return combined.sort_values(["track", "composite"], ascending=[True, False]).reset_index(
        drop=True
    )


def load_summary(run_id: str) -> pd.DataFrame:
    """Load a run's summary, or an empty frame."""
    if not run_id:
        return pd.DataFrame()
    path = RESULTS_DIR / run_id / "summary.csv"
    return pd.read_csv(path) if path.exists() else pd.DataFrame()


def load_scored(run_id: str) -> pd.DataFrame:
    """Load a run's per-sample scored rows, or an empty frame."""
    if not run_id:
        return pd.DataFrame()
    path = RESULTS_DIR / run_id / "scored.jsonl"
    return pd.read_json(path, lines=True) if path.exists() else pd.DataFrame()


def _overall(summary: pd.DataFrame) -> pd.DataFrame:
    if summary.empty:
        return summary
    return summary[summary["track"] == "ALL"].sort_values("composite", ascending=False)


def _empty_fig(title: str) -> go.Figure:
    fig = go.Figure()
    fig.update_layout(**plotly_layout(title))
    return fig


def leaderboard_fig(summary: pd.DataFrame) -> go.Figure:
    """Ranked horizontal leaderboard (OpenRouter-style): rank + model, bar by tier."""
    overall = _overall(summary)
    fig = _empty_fig("Leaderboard — composite score (all tracks)")
    if overall.empty:
        return fig
    # Highest score on top: Plotly draws horizontal bars bottom-up, so reverse.
    ranked = overall.iloc[::-1].reset_index(drop=True)
    n = len(ranked)
    labels = [f"#{n - i}  {slug}" for i, slug in enumerate(ranked["model_slug"])]
    colors = [TIER_COLORS.get(str(t), TIER_COLORS["n/a"]) for t in ranked["tier"]]
    error_x = None
    if "composite_std" in ranked and ranked["composite_std"].notna().any():
        error_x = {"type": "data", "array": ranked["composite_std"], "visible": True}
    fig.add_bar(
        x=ranked["composite"],
        y=labels,
        orientation="h",
        marker_color=colors,
        marker_line_width=0,
        error_x=error_x,
        text=[f"{v:.3f}" for v in ranked["composite"]],
        textposition="outside",
    )
    fig.update_xaxes(range=[0, 1.05], title="composite score")
    fig.update_yaxes(automargin=True)
    fig.update_layout(bargap=0.4)
    return fig


def cost_quality_fig(summary: pd.DataFrame) -> go.Figure:
    """Scatter of cost/run vs composite — surfaces best-value models.

    Cost spans an order of magnitude, so the x-axis is logarithmic to spread the
    cheaper models apart, and labels alternate above/below their marker to avoid
    overlapping when many models cluster at similar scores.
    """
    overall = _overall(summary)
    fig = _empty_fig("Cost vs. quality")
    if overall.empty:
        return fig
    positions = ["top center" if i % 2 == 0 else "bottom center" for i in range(len(overall))]
    fig.add_scatter(
        x=overall["cost_per_run"],
        y=overall["composite"],
        mode="markers+text",
        text=overall["model_slug"],
        textposition=positions,
        textfont={"size": 9},
        cliponaxis=False,
        marker={"size": 10, "color": [TIER_COLORS.get(str(t)) for t in overall["tier"]]},
        hovertemplate="%{text}<br>$%{x:.4f}/run<br>composite %{y:.3f}<extra></extra>",
    )
    # Dynamic ranges with padding so no point or edge label is clipped.
    comp = pd.to_numeric(overall["composite"], errors="coerce")
    lo = max(0.0, float(comp.min()) - 0.05)
    cost = pd.to_numeric(overall["cost_per_run"], errors="coerce")
    cost = cost[cost > 0]
    xlo = math.log10(float(cost.min())) - 0.25
    xhi = math.log10(float(cost.max())) + 0.35
    fig.update_xaxes(title="Cost per run ($, log scale)", type="log", range=[xlo, xhi])
    fig.update_yaxes(title="Composite", range=[lo, 1.0])
    return fig


def metric_bar_fig(summary: pd.DataFrame, metric: str) -> go.Figure:
    """Bar of any single metric across models (overall rollup)."""
    overall = _overall(summary)
    fig = _empty_fig(f"{metric.replace('_', ' ').title()} by model")
    if overall.empty or metric not in overall:
        return fig
    fig.add_bar(x=overall["model_slug"], y=overall[metric])
    return fig


def oneshot_fig(summary: pd.DataFrame) -> go.Figure:
    """Grouped bars: one-shot vs multi-shot pass rate per model."""
    overall = _overall(summary)
    fig = _empty_fig("One-shot vs. multi-shot pass rate")
    if overall.empty:
        return fig
    fig.add_bar(x=overall["model_slug"], y=overall["one_shot_pass_rate"], name="one-shot")
    fig.add_bar(x=overall["model_slug"], y=overall["multi_shot_pass_rate"], name="multi-shot")
    fig.update_layout(barmode="group")
    fig.update_yaxes(range=[0, 1])
    return fig


def track_heatmap_fig(summary: pd.DataFrame) -> go.Figure:
    """Heatmap of composite score across model x track."""
    fig = _empty_fig("Composite by model x track")
    if summary.empty:
        return fig
    grid = summary[summary["track"] != "ALL"].pivot(
        index="model_slug", columns="track", values="composite"
    )
    if grid.empty:
        return fig
    fig.add_heatmap(
        z=grid.values,
        x=list(grid.columns),
        y=list(grid.index),
        colorscale="Blues",
        zmin=0,
        zmax=1,
        colorbar={"title": "composite"},
    )
    return fig


def _category_composites(summary: pd.DataFrame) -> pd.DataFrame:
    """Mean composite per model within each track category (component/system)."""
    per_track = summary[summary["track"] != "ALL"].copy()
    per_track["category"] = per_track["track"].map(CATEGORY_BY_TRACK)
    grouped = per_track.groupby(["model_slug", "category"])["composite"].mean().unstack("category")
    overall = _overall(summary).set_index("model_slug")
    return grouped.reindex(overall.index)  # order by overall composite, best first


def category_bars_fig(summary: pd.DataFrame) -> go.Figure:
    """Grouped bars: each model's mean composite for component vs system tracks."""
    fig = _empty_fig("Component vs. system tests by model")
    if summary.empty:
        return fig
    cats = _category_composites(summary)
    for i, category in enumerate(("component", "system")):
        if category in cats:
            fig.add_bar(
                x=list(cats.index),
                y=cats[category],
                name=category,
                marker_color=PALETTE[i],
            )
    fig.update_layout(barmode="group")
    fig.update_yaxes(title="composite", range=[0, 1])
    return fig


def pattern_matrix_fig(scored: pd.DataFrame) -> go.Figure:
    """Heatmap of which implicit techniques each model used on e2e_advanced."""
    fig = _empty_fig("Advanced-pattern adoption by model")
    if scored.empty or "track" not in scored:
        return fig
    adv = scored[scored["track"] == "e2e_advanced"]
    cols = [f"uses_{p}" for p in PATTERN_TECHNIQUES if f"uses_{p}" in adv.columns]
    if adv.empty or not cols:
        return fig
    rates = adv.groupby("model_slug")[cols].mean()
    rates = rates.sort_values(cols, ascending=False)
    fig.add_heatmap(
        z=rates.values,
        x=[c.removeprefix("uses_") for c in cols],
        y=list(rates.index),
        colorscale="Blues",
        zmin=0,
        zmax=1,
        colorbar={"title": "adoption"},
    )
    return fig


def per_track_bars_fig(summary: pd.DataFrame) -> go.Figure:
    """Small multiples: composite per track, models in a shared overall order.

    Every subplot uses the same model order (best overall at the top), so a row is
    the same model across all tracks and a model's profile reads straight across.
    """
    if summary.empty:
        return _empty_fig("Composite by track")
    # Shared order: worst-to-best overall (Plotly draws horizontal bars bottom-up).
    order = list(_overall(summary).iloc[::-1]["model_slug"])
    tracks = sorted(t for t in summary["track"].unique() if t != "ALL")
    fig = make_subplots(rows=1, cols=len(tracks), subplot_titles=tracks, horizontal_spacing=0.03)
    for i, track in enumerate(tracks, start=1):
        sub = summary[summary["track"] == track].set_index("model_slug").reindex(order)
        fig.add_bar(
            x=sub["composite"],
            y=order,
            orientation="h",
            marker_color=PALETTE[(i - 1) % len(PALETTE)],
            showlegend=False,
            row=1,
            col=i,
        )
        fig.update_xaxes(range=[0, 1], row=1, col=i)
        if i > 1:
            fig.update_yaxes(showticklabels=False, row=1, col=i)
    fig.update_layout(**plotly_layout("Composite by track (models ordered by overall score)"))
    return fig


def scorecard_rows(summary: pd.DataFrame) -> list[dict[str, str]]:
    """Per-model overall metrics, formatted for the scorecard table."""
    overall = _overall(summary)
    rows: list[dict[str, str]] = []
    for _, r in overall.iterrows():
        row = {"model": str(r["model_slug"]), "tier": str(r.get("tier", "n/a"))}
        for m in SCORECARD_METRICS:
            row[m] = _fmt(r.get(m))
        rows.append(row)
    return rows


def available_metrics() -> list[str]:
    """Every metric the registry produces (drives the metric-explorer dropdown)."""
    return list(METRICS)


def _fmt(value: object) -> str:
    if isinstance(value, int | float):
        return "—" if (isinstance(value, float) and math.isnan(value)) else f"{value:.3g}"
    return str(value)
