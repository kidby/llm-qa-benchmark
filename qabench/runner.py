"""The generation runner: fan out over (model x track x sample), with --shots.

Generation and scoring are decoupled (like the reference harness): ``run`` only
produces ``responses.csv`` (+ a manifest). Scoring happens later in ``score``.
"""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from rich.console import Console

from qabench.checkpoint import append_row, load_done_keys, responses_path, run_dir
from qabench.config import Settings
from qabench.llm.client import build_completer
from qabench.prompts import load_prompt, prompt_hash
from qabench.scoring.context import build_context
from qabench.tracks import Track
from qabench.types import Generate, Model, Msg, Sample, ScoreContext

console = Console()


@dataclass(frozen=True)
class Task:
    """A single unit of generation work (one trial of one sample)."""

    model: Model
    track: Track
    sample: Sample
    trial: int = 0


def plan_tasks(
    models: list[Model], tracks: list[Track], *, limit: int | None, trials: int = 1
) -> list[Task]:
    """Enumerate (model x track x sample x trial) tasks, applying a per-track ``limit``."""
    tasks: list[Task] = []
    for track in tracks:
        samples = track.load_dataset()
        if limit is not None:
            samples = samples[:limit]
        for model in models:
            for sample in samples:
                for trial in range(trials):
                    tasks.append(Task(model, track, sample, trial))
    return tasks


def _generate_one(
    task: Task,
    completer: Generate,
    ctx: ScoreContext,
    *,
    shots: int,
) -> dict[str, object]:
    """Generate (with optional self-repair) and return a response row."""
    track, model, sample = task.track, task.model, task.sample
    messages = list(track.build_prompt(sample))
    use_shots = shots if (track.supports_multishot and track.feedback) else 1

    raw = ""
    attempts = 0
    tokens_in = tokens_out = 0
    cost = latency = 0.0
    error = ""

    for attempt in range(1, use_shots + 1):
        attempts = attempt
        try:
            resp = completer(model, messages)
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
            break
        raw = resp.text
        tokens_in += resp.tokens_in
        tokens_out += resp.tokens_out
        cost += resp.cost
        latency += resp.latency_s

        if use_shots == 1 or track.feedback is None:
            break
        parsed = track.parse_output(raw)
        passed, feedback = track.feedback(sample, parsed, ctx)
        if passed or attempt == use_shots:
            break
        messages.append(Msg(role="assistant", content=raw))
        messages.append(
            Msg(role="user", content=f"Your attempt did not pass. {feedback} Try again.")
        )

    return {
        "model_slug": model.slug,
        "provider": model.provider,
        "track": track.name,
        "sample_id": sample.id,
        "trial": task.trial,
        "attempts": attempts,
        "prompt_hash": prompt_hash(load_prompt(track.name)),
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "latency_s": round(latency, 3),
        "cost": round(cost, 6),
        "error": error,
        "raw_output": raw,
    }


def run(
    models: list[Model],
    tracks: list[Track],
    settings: Settings,
    *,
    run_id: str,
    limit: int | None = None,
    shots: int = 1,
    trials: int = 1,
    dry_run: bool = False,
    judge_override: Generate | None = None,
    completer_override: Generate | None = None,
) -> str:
    """Execute a generation run, writing ``responses.csv`` and a manifest.

    Args:
        models: Models to run.
        tracks: Tracks to run.
        settings: Runtime settings (concurrency, keys, ...).
        run_id: Output directory name under ``results/``.
        limit: Max samples per track.
        shots: Max attempts per sample for multi-shot-capable tracks.
        trials: Independent repeats per sample (averaged at aggregation time).
        dry_run: Print prompts and exit without calling any model.
        judge_override: Inject a fake judge (tests).
        completer_override: Inject a fake completer (tests).

    Returns:
        The run id.
    """
    tasks = plan_tasks(models, tracks, limit=limit, trials=trials)

    if dry_run:
        for task in tasks:
            msgs = task.track.build_prompt(task.sample)
            console.rule(f"{task.model.slug} / {task.track.name} / {task.sample.id}")
            for m in msgs:
                console.print(f"[bold]{m.role}[/bold]: {m.content[:400]}")
        console.print(f"\n[green]{len(tasks)} tasks planned (dry run).[/green]")
        return run_id

    done = load_done_keys(responses_path(run_id))
    pending = [
        t for t in tasks if (t.model.slug, t.track.name, t.sample.id, str(t.trial)) not in done
    ]
    _write_manifest(run_id, models, tracks, settings, shots=shots, trials=trials, total=len(tasks))

    completer = completer_override or build_completer(settings)
    ctx = build_context(settings, judge_override=judge_override)

    def work(task: Task) -> dict[str, object]:
        return _generate_one(task, completer, ctx, shots=shots)

    path = responses_path(run_id)
    with ThreadPoolExecutor(max_workers=settings.concurrency) as pool:
        for row in pool.map(work, pending):
            append_row(path, row)
            console.print(
                f"[dim]done[/dim] {row['model_slug']}/{row['track']}/{row['sample_id']}"
                + (f" [red]{row['error']}[/red]" if row["error"] else "")
            )

    console.print(f"[green]Wrote {len(pending)} responses to {path}[/green]")
    return run_id


def _write_manifest(
    run_id: str,
    models: list[Model],
    tracks: list[Track],
    settings: Settings,
    *,
    shots: int,
    trials: int,
    total: int,
) -> None:
    manifest = {
        "run_id": run_id,
        "models": [m.model_dump() for m in models],
        "tracks": [t.name for t in tracks],
        "prompt_hashes": {t.name: prompt_hash(load_prompt(t.name)) for t in tracks},
        "shots": shots,
        "trials": trials,
        "temperature": settings.temperature,
        "judge_model": settings.judge_model,
        "total_tasks": total,
    }
    (run_dir(run_id) / "run_manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
