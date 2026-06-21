"""Judge-backed scorers — thin Scorer wrappers around the LLM judge helpers."""

from __future__ import annotations

from typing import Any

from qabench.llm.judge import hallucination_check, multi_rubric_score, rubric_score
from qabench.types import Sample, ScoreContext, ScoreRow

# Structured craft criteria for the e2e auditor. Reported per-criterion plus a
# mean ``review_score``; kept separate from the execution-based headline composite.
_REVIEW_CRITERIA = {
    "readability": ("Clear test and locator names, one concern per test, readable assertions."),
    "idiomatic_playwright": (
        "Idiomatic @playwright/test: web-first assertions, fixtures where useful, "
        "resilient locators, no anti-patterns."
    ),
    "waiting_layer": (
        "Waits on the correct layer — UI assertions for rendered state, "
        "response/request waits for data — and avoids arbitrary fixed timeouts."
    ),
    "eloquence": (
        "Naming, clarity, and overall readability — does the test read well and "
        "communicate its intent concisely, without noise or needless complexity?"
    ),
}

_TEST_DESIGN_RUBRIC = (
    "Evaluate this black-box test-case suite for the given requirement. Reward "
    "coverage of equivalence partitions, boundary values, negative/error cases, "
    "and concrete (non-placeholder) inputs. Penalise redundancy and vagueness."
)
_DESIGN_RUBRIC = (
    "Evaluate the DESIGN QUALITY of this test file: clear names, one concern per "
    "test, good use of fixtures/parametrisation, readable assertions. Ignore "
    "whether it executes — judge craftsmanship only."
)
_EXPLANATION_RUBRIC = (
    "Evaluate this bug root-cause explanation for correctness and clarity given "
    "the buggy code. Reward an accurate, specific diagnosis."
)


def score_hallucination(sample: Sample, parsed: str, ctx: ScoreContext) -> ScoreRow:
    """Flag tests that call symbols absent from the source under test."""
    source = str(sample.payload.get("source", ""))
    flag, why = hallucination_check(
        ctx.judge,
        model_id=ctx.judge_model_id,
        source_code=source,
        generated_tests=parsed,
    )
    return {"hallucinated": flag, "hallucination_note": why[:200]}


def score_design(sample: Sample, parsed: str, ctx: ScoreContext) -> ScoreRow:
    """Judge the craftsmanship of a generated test file (0..1)."""
    del sample
    score, note = rubric_score(
        ctx.judge, model_id=ctx.judge_model_id, rubric=_DESIGN_RUBRIC, artifact=parsed
    )
    return {"design_judge": score, "design_note": note[:200]}


def score_test_case_design(sample: Sample, parsed: Any, ctx: ScoreContext) -> ScoreRow:
    """Judge a test-case-design suite against the requirement (0..1)."""
    requirement = str(sample.payload.get("requirement", ""))
    artifact = f"REQUIREMENT:\n{requirement}\n\nSUITE:\n{parsed}"
    score, note = rubric_score(
        ctx.judge,
        model_id=ctx.judge_model_id,
        rubric=_TEST_DESIGN_RUBRIC,
        artifact=artifact,
    )
    return {"design_judge": score, "design_note": note[:200], "passed": score >= 0.5}


def score_review(sample: Sample, parsed: str, ctx: ScoreContext) -> ScoreRow:
    """Structured craft review of an e2e test: per-criterion scores + their mean.

    Reported separately from the execution-based headline; its reliability must be
    validated against the human golden set before it is trusted.
    """
    del sample
    scores = multi_rubric_score(
        ctx.judge,
        model_id=ctx.judge_model_id,
        criteria=_REVIEW_CRITERIA,
        artifact=parsed,
    )
    row: ScoreRow = {}
    values: list[float] = []
    for name, (score, note) in scores.items():
        row[f"review_{name}"] = score
        row[f"review_{name}_note"] = note[:160]
        values.append(score)
    row["review_score"] = sum(values) / len(values) if values else float("nan")
    return row


def score_localization_explanation(sample: Sample, parsed: Any, ctx: ScoreContext) -> ScoreRow:
    """Judge the quality of a bug root-cause explanation (0..1)."""
    code = str(sample.payload.get("source", ""))
    explanation = ""
    if isinstance(parsed, dict):
        explanation = str(parsed.get("root_cause", ""))
    artifact = f"BUGGY CODE:\n{code}\n\nEXPLANATION:\n{explanation}"
    score, note = rubric_score(
        ctx.judge,
        model_id=ctx.judge_model_id,
        rubric=_EXPLANATION_RUBRIC,
        artifact=artifact,
    )
    return {"explanation_judge": score, "explanation_note": note[:200]}
