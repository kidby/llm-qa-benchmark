#!/usr/bin/env python
"""Export the dashboard result charts to transparent PNGs for the README.

Reads a run's ``summary.csv`` and renders each figure with Plotly's static export
(kaleido). Backgrounds are transparent, so the images sit cleanly on GitHub's
light or dark theme.

Usage:
    uv run python scripts/export_charts.py [run_id]   # default: newest scored run
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "dashboard"))

import qabench_dash.data as charts  # noqa: E402

IMAGE_DIR = REPO_ROOT / "docs" / "images"

# name -> (builder, source, width, height). source is "summary" or "scored".
# A height of None scales with the number of models so per-model bars stay legible.
FIGURES = {
    "leaderboard": (charts.leaderboard_fig, "summary", 1000, None),
    "cost-quality": (charts.cost_quality_fig, "summary", 900, 560),
    "track-heatmap": (charts.track_heatmap_fig, "summary", 760, 520),
    "category-bars": (charts.category_bars_fig, "summary", 1000, 480),
    "per-track": (charts.per_track_bars_fig, "summary", 1200, None),
    "pattern-adoption": (charts.pattern_matrix_fig, "scored", 720, None),
}


def main() -> None:
    """Render and write every figure for the chosen run."""
    run_id = sys.argv[1] if len(sys.argv) > 1 else (charts.list_runs() or [""])[0]
    if not run_id:
        raise SystemExit("No scored run found. Run `qabench run` then `qabench score <run_id>`.")
    summary = pd.read_csv(REPO_ROOT / "results" / run_id / "summary.csv")
    scored = charts.load_scored(run_id)
    n_models = int((summary["track"] == "ALL").sum())
    sources = {"summary": summary, "scored": scored}
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)

    for name, (builder, source, width, height) in FIGURES.items():
        fig = builder(sources[source])
        # Charts with one row per model scale their height with the model count.
        resolved_height = height if height is not None else max(360, 90 + n_models * 30)
        fig.update_layout(width=width, height=resolved_height)
        out = IMAGE_DIR / f"{name}.png"
        fig.write_image(out, scale=2)
        print(f"wrote {out.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
