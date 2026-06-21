"""Full run -> score -> report pipeline, fully offline (fake LLM, local sandbox)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
from qabench.checkpoint import responses_path, scored_path, summary_path
from qabench.config import RESULTS_DIR, Settings
from qabench.llm import make_fake
from qabench.report import render
from qabench.runner import run
from qabench.score import score
from qabench.tracks import TRACKS
from qabench.types import Model, Msg

GOOD_FIZZBUZZ = """```python
from fizzbuzz import fizzbuzz
import pytest
def test_all():
    assert fizzbuzz(3) == 'Fizz'
    assert fizzbuzz(5) == 'Buzz'
    assert fizzbuzz(15) == 'FizzBuzz'
    assert fizzbuzz(2) == '2'
def test_validation():
    with pytest.raises(ValueError):
        fizzbuzz(0)
```"""


GOOD_DISCOUNT = """```python
from discount import apply_discount
import pytest
def test_all():
    assert apply_discount(100, 10) == 90.0
    assert apply_discount(100, 0) == 100.0
    assert apply_discount(9.99, 33) == 6.69
def test_validation():
    with pytest.raises(ValueError):
        apply_discount(-1, 10)
    with pytest.raises(ValueError):
        apply_discount(100, 101)
```"""


def _responder(model: Model, messages: list[Msg]) -> str:
    user = messages[-1].content
    if "fizzbuzz" in user:
        return GOOD_FIZZBUZZ
    if "apply_discount" in user:
        return GOOD_DISCOUNT
    if "binary_search" in user:
        fix = "    while lo <= hi:"
        return f'```json\n{{"line": 9, "root_cause": "bound", "proposed_fix": "{fix}"}}\n```'
    return '```json\n{"test_cases": []}\n```'


def test_full_pipeline(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("qabench.checkpoint.RESULTS_DIR", tmp_path)
    settings = Settings(sandbox="local", concurrency=2)
    models = [Model(slug="fake", id="fake", provider="openrouter")]
    tracks = [TRACKS["unit_test_gen"], TRACKS["bug_localization"]]
    fake = make_fake(_responder)
    judge = make_fake('{"score": 0.8, "rationale": "ok", "hallucinated": false}')

    run(
        models, tracks, settings, run_id="t", limit=1, completer_override=fake, judge_override=judge
    )
    assert responses_path("t").exists()
    # responses.jsonl is valid JSONL: every non-empty line parses to an object.
    import json

    lines = [ln for ln in responses_path("t").read_text().splitlines() if ln.strip()]
    assert lines and all(isinstance(json.loads(ln), dict) for ln in lines)

    summary = score("t", settings, judge_override=judge)
    assert scored_path("t").exists()
    assert summary_path("t").exists()

    overall = summary[summary["track"] == "ALL"].iloc[0]
    assert overall["tier"] in {"A", "B", "C"}

    unit = summary[summary["track"] == "unit_test_gen"].iloc[0]
    assert unit["false_negative_rate"] == 0.0  # good suite kills the mutant
    assert unit["false_positive_rate"] == 0.0

    report = render("t")
    assert "Leaderboard" in report


def test_incremental_scoring_only_scores_new_rows(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("qabench.checkpoint.RESULTS_DIR", tmp_path)
    settings = Settings(sandbox="local", concurrency=2)
    models = [Model(slug="fake", id="fake", provider="openrouter")]
    fake = make_fake(_responder)
    judge = make_fake('{"score": 0.8, "rationale": "ok", "hallucinated": false}')

    # Score one sample, then add a second response and re-score incrementally.
    run(models, [TRACKS["unit_test_gen"]], settings, run_id="i", limit=1, completer_override=fake)
    score("i", settings, judge_override=judge)
    first = scored_path("i").read_text()
    n_first = len([ln for ln in first.splitlines() if ln.strip()])

    run(models, [TRACKS["unit_test_gen"]], settings, run_id="i", limit=2, completer_override=fake)
    score("i", settings, judge_override=judge)
    after = scored_path("i").read_text()
    n_after = len([ln for ln in after.splitlines() if ln.strip()])

    assert n_after > n_first  # the new sample was scored
    assert after.startswith(first)  # earlier scored rows are byte-identical (not re-scored)


def test_rescore_recomputes_all(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("qabench.checkpoint.RESULTS_DIR", tmp_path)
    settings = Settings(sandbox="local", concurrency=2)
    models = [Model(slug="fake", id="fake", provider="openrouter")]
    fake = make_fake(_responder)
    judge = make_fake('{"score": 0.8, "rationale": "ok", "hallucinated": false}')

    run(models, [TRACKS["unit_test_gen"]], settings, run_id="rs", limit=1, completer_override=fake)
    score("rs", settings, judge_override=judge)
    n1 = len([ln for ln in scored_path("rs").read_text().splitlines() if ln.strip()])
    score("rs", settings, rescore=True, judge_override=judge)
    n2 = len([ln for ln in scored_path("rs").read_text().splitlines() if ln.strip()])
    assert n1 == n2 == 1  # rescore rebuilds rather than duplicating


def test_resume_skips_completed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("qabench.checkpoint.RESULTS_DIR", tmp_path)
    settings = Settings(sandbox="local", concurrency=2)
    models = [Model(slug="fake", id="fake", provider="openrouter")]
    tracks = [TRACKS["unit_test_gen"]]
    fake = make_fake(_responder)

    run(models, tracks, settings, run_id="r", limit=1, completer_override=fake)
    first = pd.read_json(responses_path("r"), lines=True)
    run(models, tracks, settings, run_id="r", limit=1, completer_override=fake)
    second = pd.read_json(responses_path("r"), lines=True)
    assert len(first) == len(second)  # nothing re-added on resume


def test_dry_run_calls_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("qabench.checkpoint.RESULTS_DIR", tmp_path)
    settings = Settings(sandbox="local")
    models = [Model(slug="fake", id="fake", provider="openrouter")]

    def boom(_model: Model, _messages: list[Msg]) -> str:
        raise AssertionError("should not be called in dry run")

    run(
        models,
        [TRACKS["unit_test_gen"]],
        settings,
        run_id="d",
        dry_run=True,
        completer_override=make_fake(boom),
    )
    assert not (RESULTS_DIR / "d" / "responses.csv").exists()
