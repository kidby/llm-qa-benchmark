"""Batch re-judge: record/replay key matching and end-to-end with a fake batch."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest
from qabench.config import Settings
from qabench.llm.batch import RecordingJudge, ReplayJudge, _message_key, batch_rejudge
from qabench.tracks import TRACKS
from qabench.types import Model, Msg


def _model() -> Model:
    return Model(slug="judge", id="claude-opus-4-8", provider="openrouter", label="judge")


def test_record_then_replay_round_trips() -> None:
    rec = RecordingJudge()
    msgs = [Msg(role="system", content="You judge."), Msg(role="user", content="Rate X")]
    rec(_model(), msgs)
    key = _message_key(_model(), msgs)
    assert key in rec.recorded and len(key) == 64
    # The replay judge returns the batched text for the same prompt.
    rep = ReplayJudge({key: '{"score": 0.9, "rationale": "good"}'})
    assert "0.9" in rep(_model(), msgs).text
    # An unseen prompt falls back to an empty-but-parseable payload.
    assert rep(_model(), [Msg(role="user", content="other")]).text == "{}"


def test_batch_rejudge_refreshes_judge_columns(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A minimal unit_test_gen run: one response + one scored row whose judge columns
    # (design_judge, hallucinated) errored on the previous run.
    from qabench import checkpoint

    results = tmp_path / "results" / "r"
    results.mkdir(parents=True)
    # The path helpers read checkpoint.RESULTS_DIR live, so patching it redirects them.
    monkeypatch.setattr(checkpoint, "RESULTS_DIR", tmp_path / "results")

    sample_id = TRACKS["unit_test_gen"].load_dataset()[0].id
    suite = "from x import y\n\ndef test_it():\n    assert y() == 1\n"
    resp = {
        "model_slug": "m",
        "track": "unit_test_gen",
        "sample_id": sample_id,
        "trial": 0,
        "raw_output": f"```python\n{suite}\n```",
    }
    scored = {
        "model_slug": "m",
        "track": "unit_test_gen",
        "sample_id": sample_id,
        "trial": 0,
        "passed": True,
        "recall": 0.5,  # an execution column that must survive
        "score_design_error": "402",
        "score_hallucination_error": "402",
    }
    (results / "responses.jsonl").write_text(json.dumps(resp) + "\n")
    (results / "scored.jsonl").write_text(json.dumps(scored) + "\n")

    # Fake batch: answer every collected prompt with a fixed JSON judge reply.
    def fake_batch(prompts: dict[str, list[Msg]]) -> dict[str, str]:
        assert prompts, "scorers should have recorded at least one judge prompt"
        return dict.fromkeys(prompts, '{"score": 0.8, "rationale": "ok", "hallucinated": false}')

    summary = batch_rejudge("r", Settings(), run_batch=fake_batch)

    rejudged = pd.read_json(results / "scored.jsonl", lines=True)
    row = rejudged.iloc[0]
    assert "score_design_error" not in rejudged.columns  # stale error dropped
    assert row["design_judge"] == 0.8  # judge column refreshed
    assert bool(row["passed"]) is True and row["recall"] == 0.5  # execution preserved
    assert not summary.empty
