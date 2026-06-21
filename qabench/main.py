"""Command-line interface for the QA benchmark.

Subcommands mirror the reference harness: ``list-models`` / ``show-prompt`` /
``run`` / ``resume`` / ``score`` / ``report`` / ``dashboard``.
"""

from __future__ import annotations

import subprocess
import sys
from datetime import UTC, datetime

import typer
from rich.console import Console
from rich.table import Table

from qabench.config import load_settings
from qabench.models import load_models, select_models
from qabench.prompts import available_tracks, load_prompt, prompt_hash

app = typer.Typer(
    add_completion=False,
    help="Execution-based LLM benchmark for QA & test automation.",
    no_args_is_help=True,
)
console = Console()


@app.command("list-models")
def list_models() -> None:
    """Print the model registry."""
    models = load_models()
    table = Table(title="Model registry", header_style="bold")
    table.add_column("slug")
    table.add_column("provider")
    table.add_column("model id")
    table.add_column("params (B)", justify="right")
    table.add_column("$/Mtok in", justify="right")
    table.add_column("$/Mtok out", justify="right")
    table.add_column("default", justify="center")
    for m in models:
        table.add_row(
            m.slug,
            m.provider,
            m.id,
            f"{m.params_b:g}" if m.params_b is not None else "-",
            f"{m.input_cost_per_mtok:g}",
            f"{m.output_cost_per_mtok:g}",
            "+" if not m.skip_by_default else "-",
        )
    console.print(table)


@app.command("show-prompt")
def show_prompt(track: str = typer.Option("all", help="Track name, or 'all'.")) -> None:
    """Display the system prompt(s) and their hashes."""
    tracks = available_tracks()
    names = tracks if track == "all" else [track]
    for name in names:
        if name not in tracks:
            raise typer.BadParameter(f"Unknown track: {name}. Choices: {', '.join(tracks)}")
        text = load_prompt(name)
        console.rule(f"[bold]{name}[/bold]  (hash {prompt_hash(text)})")
        console.print(text)


def _new_run_id() -> str:
    return "run-" + datetime.now(UTC).strftime("%Y%m%d-%H%M%S")


@app.command("run")
def run_cmd(
    track: str = typer.Option("all", help="Track(s): 'all' or comma-separated names."),
    models: str = typer.Option("all", help="Models: 'all', '*', or comma-separated slugs."),
    limit: int | None = typer.Option(None, help="Max samples per track."),
    shots: int = typer.Option(1, help="Max attempts for multi-shot-capable tracks."),
    trials: int = typer.Option(1, help="Repeats per sample; averaged at scoring."),
    concurrency: int | None = typer.Option(None, help="Override request concurrency."),
    temperature: float | None = typer.Option(None, help="Sampling temperature for generation."),
    run_id: str | None = typer.Option(None, help="Run id (default: timestamp)."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Print prompts, call nothing."),
) -> None:
    """Generate model outputs into ``results/<run_id>/responses.csv``."""
    from qabench.runner import run as run_benchmark
    from qabench.tracks import select_tracks

    settings = load_settings()
    updates: dict[str, object] = {}
    if concurrency is not None:
        updates["concurrency"] = concurrency
    if temperature is not None:
        updates["temperature"] = temperature
    if updates:
        settings = settings.model_copy(update=updates)
    selected_models = select_models(load_models(), models)
    selected_tracks = select_tracks(track)
    rid = run_id or _new_run_id()
    run_benchmark(
        selected_models,
        selected_tracks,
        settings,
        run_id=rid,
        limit=limit,
        shots=shots,
        trials=trials,
        dry_run=dry_run,
    )
    if not dry_run:
        console.print(f"[bold]Run id:[/bold] {rid}")


@app.command("resume")
def resume_cmd(
    run_id: str = typer.Argument(..., help="Existing run id to resume."),
    track: str = typer.Option("all"),
    models: str = typer.Option("all"),
    limit: int | None = typer.Option(None),
    shots: int = typer.Option(1),
    trials: int = typer.Option(1),
) -> None:
    """Resume a run, skipping already-completed (model, track, sample, trial) rows."""
    from qabench.runner import run as run_benchmark
    from qabench.tracks import select_tracks

    settings = load_settings()
    run_benchmark(
        select_models(load_models(), models),
        select_tracks(track),
        settings,
        run_id=run_id,
        limit=limit,
        shots=shots,
        trials=trials,
    )


@app.command("score")
def score_cmd(
    run_id: str = typer.Argument(..., help="Run id to score."),
    rescore: bool = typer.Option(
        False, "--rescore", help="Recompute all rows instead of only new ones."
    ),
) -> None:
    """Execute + judge a run's outputs, writing scored.jsonl and summary.csv.

    Incremental by default: only responses not already scored are run.
    """
    from qabench.report import render
    from qabench.score import score

    score(run_id, load_settings(), rescore=rescore)
    render(run_id)
    console.print("[green]Wrote report.md[/green]")


@app.command("rejudge")
def rejudge_cmd(run_id: str = typer.Argument(..., help="Run id to re-judge.")) -> None:
    """Re-run only the LLM judges via the Anthropic Message Batches API (50% price).

    Keeps the execution and static columns in scored.jsonl, refreshes the judge
    columns, and re-aggregates. Needs ANTHROPIC_API_KEY and the `anthropic` extra
    (`uv sync --extra judge`). Generation still uses OpenRouter.
    """
    from qabench.llm.batch import batch_rejudge
    from qabench.report import render

    batch_rejudge(run_id, load_settings())
    render(run_id)
    console.print("[green]Wrote report.md[/green]")


@app.command("report")
def report_cmd(run_id: str = typer.Argument(..., help="Run id to render.")) -> None:
    """Render report.md from an already-scored run."""
    from qabench.report import render

    console.print(render(run_id))


@app.command("dashboard")
def dashboard_cmd(
    run: str | None = typer.Option(None, help="Run id to pre-select."),
    port: int = typer.Option(3000, help="Port to serve the dashboard on."),
) -> None:
    """Launch the Reflex + Plotly results dashboard."""
    from qabench.config import REPO_ROOT

    env_run = f"QABENCH_RUN={run} " if run else ""
    console.print(f"[bold]Starting dashboard on http://localhost:{port}[/bold]")
    console.print(f"[dim]{env_run}reflex run --frontend-port {port}[/dim]")
    cmd = [sys.executable, "-m", "reflex", "run", "--frontend-port", str(port)]
    env = {"QABENCH_RUN": run} if run else None
    subprocess.run(cmd, cwd=REPO_ROOT / "dashboard", env=_merged_env(env), check=False)


def _merged_env(extra: dict[str, str] | None) -> dict[str, str]:
    import os

    return {**os.environ, **(extra or {})}


if __name__ == "__main__":
    app()
