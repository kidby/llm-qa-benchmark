"""Render a Markdown report from a run's summary.csv."""

from __future__ import annotations

import json
import math

import pandas as pd

from qabench.checkpoint import read_csv, report_path, run_dir, summary_path

_LEADERBOARD_COLS = [
    ("tier", "Tier"),
    ("composite", "Composite"),
    ("composite_std", "±"),
    ("n_trials", "Trials"),
    ("multi_shot_pass_rate", "Pass"),
    ("recall", "Mut-kill"),
    ("coverage", "Cov%"),
    ("false_positive_rate", "FP"),
    ("hallucination_rate", "Halluc"),
    ("cost_per_run", "$/run"),
    ("tok_per_s", "tok/s"),
]


def _fmt(value: object) -> str:
    if isinstance(value, float):
        return "—" if math.isnan(value) else f"{value:.3g}"
    return str(value)


def _table(df: pd.DataFrame, cols: list[tuple[str, str]]) -> str:
    headers = ["Model", *[label for _, label in cols]]
    lines = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    for _, row in df.iterrows():
        cells = [str(row["model_slug"])] + [_fmt(row.get(key)) for key, _ in cols]
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def render(run_id: str) -> str:
    """Build the Markdown report and write it to ``report.md``."""
    summary = read_csv(summary_path(run_id))
    manifest_path = run_dir(run_id) / "run_manifest.json"
    manifest = (
        json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    )

    parts = [f"# QA Benchmark report — `{run_id}`", ""]
    if manifest:
        parts.append(
            f"Tracks: {', '.join(manifest.get('tracks', []))} · "
            f"shots: {manifest.get('shots', 1)} · "
            f"judge: `{manifest.get('judge_model', '')}`"
        )
        parts.append("")

    if summary.empty:
        parts.append("_No scored results yet._")
        text = "\n".join(parts)
        report_path(run_id).write_text(text, encoding="utf-8")
        return text

    overall = summary[summary["track"] == "ALL"].sort_values("composite", ascending=False)
    parts += ["## Leaderboard (all tracks)", "", _table(overall, _LEADERBOARD_COLS), ""]

    for track in sorted(t for t in summary["track"].unique() if t != "ALL"):
        sub = summary[summary["track"] == track].sort_values("composite", ascending=False)
        parts += [f"## Track: `{track}`", "", _table(sub, _LEADERBOARD_COLS), ""]

    parts += [
        "## Notes",
        "",
        "- **FP** = tests failing on correct code (false alarms). "
        "**Mut-kill** = mutants caught (recall). Lower **Halluc** is better.",
        "- Tiers: **A** ≥ 0.80, **B** ≥ 0.60, **C** < 0.60 (composite).",
        "- Categories: **component** (unit_test_gen, bug_localization, test_case_design) and "
        "**system** (e2e_ui, e2e_advanced).",
        "",
    ]
    text = "\n".join(parts)
    report_path(run_id).write_text(text, encoding="utf-8")
    return text
