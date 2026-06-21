"""LLM judges for rubric scoring and hallucination detection.

These wrap a ``Generate`` so tests can inject a fake judge with no network. In
production the judge runs through OpenRouter at temperature 0.
"""

from __future__ import annotations

import json
import re

from qabench.types import Generate, Model, Msg

_JSON_BLOCK = re.compile(r"\{.*\}", re.DOTALL)


def _judge_model(model_id: str) -> Model:
    return Model(slug="judge", id=model_id, provider="openrouter", label="judge")


def _extract_json(text: str) -> dict[str, object]:
    match = _JSON_BLOCK.search(text)
    if not match:
        return {}
    try:
        result: dict[str, object] = json.loads(match.group(0))
        return result
    except json.JSONDecodeError:
        return {}


def rubric_score(
    generate: Generate,
    *,
    model_id: str,
    rubric: str,
    artifact: str,
) -> tuple[float, str]:
    """Score an artifact against a rubric, returning ``(score_0_1, rationale)``."""
    prompt = (
        f"{rubric}\n\nReturn ONLY JSON: "
        '{"score": <float 0..1>, "rationale": "<short>"}\n\n'
        f"Artifact to evaluate:\n\n{artifact}"
    )
    messages = [
        Msg(role="system", content="You are a strict, fair QA evaluator."),
        Msg(role="user", content=prompt),
    ]
    resp = generate(_judge_model(model_id), messages)
    data = _extract_json(resp.text)
    raw_score = data.get("score", 0.0)
    score = float(raw_score) if isinstance(raw_score, int | float) else 0.0
    rationale = str(data.get("rationale", ""))
    return max(0.0, min(1.0, score)), rationale


def multi_rubric_score(
    generate: Generate,
    *,
    model_id: str,
    criteria: dict[str, str],
    artifact: str,
) -> dict[str, tuple[float, str]]:
    """Score an artifact on several criteria in one call.

    Returns ``{criterion: (score_0_1, note)}`` for every requested criterion; a
    criterion missing from the judge's reply defaults to ``(0.0, "")``.
    """
    lines = "\n".join(f"- {name}: {desc}" for name, desc in criteria.items())
    shape = ", ".join(f'"{name}": {{"score": <0..1>, "note": "<short>"}}' for name in criteria)
    prompt = (
        "Evaluate the artifact below against EACH criterion. Score each from 0.0 to "
        "1.0 independently.\n\nCriteria:\n"
        f"{lines}\n\nReturn ONLY JSON of this shape:\n{{{shape}}}\n\n"
        f"Artifact to evaluate:\n\n{artifact}"
    )
    messages = [
        Msg(role="system", content="You are a strict, fair QA evaluator."),
        Msg(role="user", content=prompt),
    ]
    resp = generate(_judge_model(model_id), messages)
    data = _extract_json(resp.text)
    result: dict[str, tuple[float, str]] = {}
    for name in criteria:
        entry = data.get(name)
        if isinstance(entry, dict):
            raw = entry.get("score", 0.0)
            score = float(raw) if isinstance(raw, int | float) else 0.0
            note = str(entry.get("note", ""))
        else:
            score, note = 0.0, ""
        result[name] = (max(0.0, min(1.0, score)), note)
    return result


def hallucination_check(
    generate: Generate,
    *,
    model_id: str,
    source_code: str,
    generated_tests: str,
) -> tuple[bool, str]:
    """Decide whether ``generated_tests`` reference symbols absent from ``source_code``.

    Returns ``(hallucinated, rationale)``.
    """
    prompt = (
        "Below is a module ('SOURCE') and a test file ('TESTS') written for it. "
        "Does TESTS call functions, methods, classes, or attributes that do NOT "
        "exist in SOURCE (i.e. hallucinated APIs)? Ignore standard library and "
        "test-framework usage.\n\n"
        'Return ONLY JSON: {"hallucinated": <true|false>, "rationale": "<short>"}\n\n'
        f"SOURCE:\n{source_code}\n\nTESTS:\n{generated_tests}"
    )
    messages = [
        Msg(role="system", content="You are a precise static-analysis assistant."),
        Msg(role="user", content=prompt),
    ]
    resp = generate(_judge_model(model_id), messages)
    data = _extract_json(resp.text)
    return bool(data.get("hallucinated", False)), str(data.get("rationale", ""))
