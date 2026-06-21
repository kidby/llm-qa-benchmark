"""Anthropic-direct batch re-judge: re-run only the LLM judges, at 50% price.

The judges are an ideal batch workload — offline, deterministic (temperature 0),
high volume, not latency-sensitive — so the Anthropic Message Batches API runs
them at half the standard price. Generation stays on OpenRouter; only the judges
go direct to Anthropic here.

Design (record -> batch -> replay) so the existing judge scorers are reused
unchanged: a ``RecordingJudge`` captures every prompt the scorers build, the
prompts are submitted as one batch, and a ``ReplayJudge`` feeds the results back
through the same scorers so their parsing logic runs verbatim.
"""

from __future__ import annotations

import hashlib
import json
import math
import time
from collections.abc import Callable
from pathlib import Path
from typing import cast

import pandas as pd
from rich.console import Console

from qabench.aggregate import summarize
from qabench.checkpoint import (
    KEY_COLUMNS,
    read_jsonl,
    responses_path,
    scored_path,
    summary_path,
)
from qabench.config import Settings
from qabench.score import _samples_by_track
from qabench.scoring.context import build_context
from qabench.tracks import TRACKS
from qabench.types import Model, Msg, Response, Scorer

console = Console()

# Scorers that call the LLM judge (everything else is execution/static and already
# present in scored.jsonl). Only these are re-run here.
_JUDGE_SCORER_NAMES = {
    "score_design",
    "score_review",
    "score_hallucination",
    "score_test_case_design",
    "score_localization_explanation",
}

# Columns owned by the judges. On apply we drop any of these the current track no
# longer produces (e.g. ``design_judge`` on e2e rows after design was removed there)
# so stale values from a previous run don't linger. ``passed`` is intentionally
# excluded — it is shared with the execution scorers.
_JUDGE_COLS = {
    "design_judge",
    "design_note",
    "hallucinated",
    "hallucination_note",
    "explanation_judge",
    "explanation_note",
}


def _is_judge_col(name: str) -> bool:
    return name in _JUDGE_COLS or name.startswith("review_")


def _message_key(model: Model, messages: list[Msg]) -> str:
    """Stable id for a judge prompt — same (model, messages) always hashes the same.

    The scorers build identical messages in the record and replay passes, so this
    key matches across passes and also dedupes identical prompts across rows.
    """
    payload = json.dumps(
        [model.id, [(m.role, m.content) for m in messages]],
        ensure_ascii=False,
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()  # 64 hex chars (valid custom_id)


class RecordingJudge:
    """Generate stand-in that records each prompt and returns a parseable dummy."""

    def __init__(self) -> None:
        self.recorded: dict[str, list[Msg]] = {}

    def __call__(self, model: Model, messages: list[Msg]) -> Response:
        """Record the prompt; return a parseable dummy (its result is discarded)."""
        self.recorded[_message_key(model, messages)] = messages
        return Response(text="{}")


class ReplayJudge:
    """Generate stand-in that returns the batched judge text for a recorded prompt."""

    def __init__(self, results: dict[str, str]) -> None:
        self.results = results

    def __call__(self, model: Model, messages: list[Msg]) -> Response:
        """Return the batched judge text for the matching prompt (else empty JSON)."""
        return Response(text=self.results.get(_message_key(model, messages), "{}"))


def _anthropic_run_batch(
    api_key: str, model: str, prompts: dict[str, list[Msg]], *, poll_seconds: int = 30
) -> dict[str, str]:
    """Submit prompts to the Message Batches API, poll, and return ``{key: text}``."""
    try:
        import anthropic
        from anthropic.types import MessageParam
        from anthropic.types.message_create_params import MessageCreateParamsNonStreaming
        from anthropic.types.messages.batch_create_params import Request
    except ModuleNotFoundError as exc:  # pragma: no cover - import guard
        raise RuntimeError(
            "The batch re-judge needs the Anthropic SDK. Install it with "
            "`uv sync --extra judge` (or `pip install anthropic`)."
        ) from exc

    client = anthropic.Anthropic(api_key=api_key)
    requests: list[Request] = []
    for key, messages in prompts.items():
        system = "\n".join(m.content for m in messages if m.role == "system")
        # The `!= "system"` guard narrows m.role to Literal["user", "assistant"],
        # so each dict is a valid MessageParam (Anthropic takes system separately).
        payload: list[MessageParam] = [
            {"role": m.role, "content": m.content} for m in messages if m.role != "system"
        ]
        requests.append(
            Request(
                custom_id=key,
                params=MessageCreateParamsNonStreaming(
                    model=model, max_tokens=1024, system=system, messages=payload
                ),
            )
        )
    batch = client.messages.batches.create(requests=requests)
    console.print(f"[cyan]Submitted batch {batch.id} ({len(requests)} judge prompts).[/cyan]")
    while True:
        current = client.messages.batches.retrieve(batch.id)
        if current.processing_status == "ended":
            break
        console.print(f"[dim]batch {batch.id}: {current.processing_status}…[/dim]")
        time.sleep(poll_seconds)

    out: dict[str, str] = {}
    for result in client.messages.batches.results(batch.id):
        if result.result.type == "succeeded":
            blocks = result.result.message.content
            out[result.custom_id] = next((b.text for b in blocks if b.type == "text"), "{}")
        else:
            out[result.custom_id] = "{}"  # errored/expired — leave the judge fields empty
    console.print(f"[green]Batch complete: {len(out)} results.[/green]")
    return out


def batch_rejudge(
    run_id: str,
    settings: Settings,
    *,
    run_batch: Callable[[dict[str, list[Msg]]], dict[str, str]] | None = None,
) -> pd.DataFrame:
    """Re-run only the LLM judges for a run via one Anthropic batch, then re-aggregate.

    Execution and static columns in ``scored.jsonl`` are kept as-is; only the judge
    columns are refreshed. ``run_batch`` is injectable for tests; by default it
    submits to the Anthropic Message Batches API.
    """
    if run_batch is None:
        if not settings.anthropic_api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is required for the batch re-judge.")

        def run_batch(prompts: dict[str, list[Msg]]) -> dict[str, str]:
            return _anthropic_run_batch(
                settings.anthropic_api_key, settings.anthropic_judge_model, prompts
            )

    scored = read_jsonl(scored_path(run_id))
    responses = read_jsonl(responses_path(run_id))
    if scored.empty:
        console.print("[yellow]Nothing scored to re-judge.[/yellow]")
        return pd.DataFrame()

    def _raw(r: pd.Series) -> str:
        val = r.get("raw_output")
        return "" if pd.isna(val) else str(val)

    raw_by_key = {
        tuple(str(r.get(c)) for c in KEY_COLUMNS): _raw(r) for _, r in responses.iterrows()
    }
    samples = _samples_by_track()
    rows = cast("list[dict[str, object]]", scored.to_dict("records"))

    def judge_scorers(track_name: str) -> list[Scorer]:
        return [
            s
            for s in TRACKS[track_name].scorers
            if getattr(s, "__name__", "") in _JUDGE_SCORER_NAMES
        ]

    def parsed_for(row: dict[str, object]) -> object:
        track = TRACKS[str(row["track"])]
        key = tuple(str(row.get(c)) for c in KEY_COLUMNS)
        return track.parse_output(raw_by_key.get(key, ""))

    # Pass 1 — record every judge prompt the scorers build.
    recorder = RecordingJudge()
    ctx_rec = build_context(settings, judge_override=recorder)
    for row in rows:
        track_name = str(row["track"])
        sample = samples[track_name][str(row["sample_id"])]
        parsed = parsed_for(row)
        for scorer in judge_scorers(track_name):
            scorer(sample, parsed, ctx_rec)
    console.print(f"[cyan]Collected {len(recorder.recorded)} unique judge prompts.[/cyan]")

    results = run_batch(recorder.recorded)

    # Pass 2 — replay the batched results through the same scorers and merge.
    ctx_rep = build_context(settings, judge_override=ReplayJudge(results))
    for row in rows:
        track_name = str(row["track"])
        sample = samples[track_name][str(row["sample_id"])]
        parsed = parsed_for(row)
        fresh: dict[str, object] = {}
        for scorer in judge_scorers(track_name):
            fresh.update(scorer(sample, parsed, ctx_rep))
        for col in list(row):
            if col.endswith("_error") or (_is_judge_col(col) and col not in fresh):
                del row[col]
        row.update(fresh)

    _write_jsonl(scored_path(run_id), rows)
    summary = summarize(pd.DataFrame(rows))
    summary.to_csv(summary_path(run_id), index=False)
    console.print(f"[green]Re-judged {len(rows)} rows -> {summary_path(run_id)}[/green]")
    return summary


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    """Rewrite scored.jsonl, dropping NaN keys to keep rows sparse like the original."""
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            clean = {k: v for k, v in row.items() if not (isinstance(v, float) and math.isnan(v))}
            fh.write(json.dumps(clean) + "\n")
