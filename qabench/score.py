"""Scoring orchestrator: responses.jsonl -> scored.jsonl -> summary.csv.

Re-parses each stored model output and runs the track's scorer functions through
the shared scoring context, then aggregates with the metric registry. Scoring is
incremental: rows already present in ``scored.jsonl`` are skipped (use
``rescore=True`` to recompute everything).
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pandas as pd
from rich.console import Console

from qabench.aggregate import summarize
from qabench.checkpoint import (
    KEY_COLUMNS,
    append_row,
    load_done_keys,
    read_jsonl,
    responses_path,
    scored_path,
    summary_path,
)
from qabench.config import Settings
from qabench.scoring.context import build_context
from qabench.tracks import TRACKS
from qabench.types import Generate, Sample, ScoreContext

console = Console()


def _row_key(row: pd.Series) -> tuple[str, ...]:
    return tuple(str(row.get(col)) for col in KEY_COLUMNS)


def _samples_by_track() -> dict[str, dict[str, Sample]]:
    return {name: {s.id: s for s in track.load_dataset()} for name, track in TRACKS.items()}


def _score_row(
    row: pd.Series, samples: dict[str, dict[str, Sample]], ctx: ScoreContext
) -> dict[str, object]:
    track_name = str(row["track"])
    track = TRACKS[track_name]
    sample = samples[track_name][str(row["sample_id"])]
    raw = "" if pd.isna(row.get("raw_output")) else str(row["raw_output"])
    parsed = track.parse_output(raw)

    out: dict[str, object] = {
        "model_slug": row["model_slug"],
        "provider": row.get("provider", ""),
        "track": track_name,
        "sample_id": row["sample_id"],
        "trial": int(row.get("trial", 0) or 0),
        "attempts": int(row.get("attempts", 1) or 1),
        "tokens_in": row.get("tokens_in", 0),
        "tokens_out": row.get("tokens_out", 0),
        "latency_s": row.get("latency_s", 0.0),
        "cost": row.get("cost", 0.0),
    }
    for scorer in track.scorers:
        try:
            out.update(scorer(sample, parsed, ctx))
        except Exception as exc:
            name = getattr(scorer, "__name__", "scorer")
            out[f"{name}_error"] = f"{type(exc).__name__}: {exc}"
    return out


def score(
    run_id: str,
    settings: Settings,
    *,
    rescore: bool = False,
    judge_override: Generate | None = None,
) -> pd.DataFrame:
    """Score a run's responses incrementally and write ``summary.csv``.

    Only responses not already in ``scored.jsonl`` are scored and appended, then
    the full scored set is re-aggregated. ``rescore=True`` recomputes everything.
    """
    responses = read_jsonl(responses_path(run_id))
    if responses.empty:
        console.print("[yellow]No responses to score.[/yellow]")
        return pd.DataFrame()

    scored_file = scored_path(run_id)
    if rescore and scored_file.exists():
        scored_file.unlink()
    done = set() if rescore else load_done_keys(scored_file)
    pending = [row for _, row in responses.iterrows() if _row_key(row) not in done]

    if pending:
        samples = _samples_by_track()
        ctx = build_context(settings, judge_override=judge_override)

        # Scorers are I/O-bound (sandbox runs, judge calls), so run them concurrently.
        def score_one(row: pd.Series) -> dict[str, object]:
            result = _score_row(row, samples, ctx)
            console.print(
                f"[dim]scored[/dim] {row['model_slug']}/{row['track']}/{row['sample_id']}"
            )
            return result

        with ThreadPoolExecutor(max_workers=settings.concurrency) as pool:
            for result in pool.map(score_one, pending):
                append_row(scored_file, result)
        console.print(f"[green]Scored {len(pending)} new row(s).[/green]")
    else:
        console.print("[green]Nothing new to score; re-aggregating.[/green]")

    scored = read_jsonl(scored_file)
    summary = summarize(scored)
    summary.to_csv(summary_path(run_id), index=False)
    console.print(f"[green]Summary ({len(scored)} rows) -> {summary_path(run_id)}[/green]")
    return summary
