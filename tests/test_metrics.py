from __future__ import annotations

import math

import pandas as pd
from qabench.scoring.metrics import (
    METRICS,
    composite,
    f1,
    false_negative_rate,
    false_positive_rate,
    one_shot_pass_rate,
    precision,
    recall,
    tier,
)


def _unit_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "sample_id": "a",
                "tests_total": 5,
                "tests_failing_on_correct": 0,
                "mutants_total": 4,
                "mutants_surviving": 1,
                "mutants_killed": 3,
                "coverage_pct": 90.0,
                "runs_and_valid": True,
                "passed": True,
                "attempts": 1,
                "hallucinated": False,
            }
        ]
    )


def test_false_positive_rate() -> None:
    df = _unit_frame()
    df.loc[0, "tests_failing_on_correct"] = 1
    assert false_positive_rate(df) == 0.2


def test_false_negative_rate_and_recall() -> None:
    df = _unit_frame()
    assert false_negative_rate(df) == 0.25
    assert recall(df) == 0.75


def test_precision_and_f1() -> None:
    df = _unit_frame()  # tp=3 killed, fp=0 failing
    assert precision(df) == 1.0
    assert math.isclose(f1(df), 2 * 1.0 * 0.75 / 1.75)


def test_metrics_missing_columns_return_nan() -> None:
    empty = pd.DataFrame([{"sample_id": "a"}])
    assert math.isnan(false_positive_rate(empty))
    assert math.isnan(recall(empty))


def test_one_shot_vs_multishot_gap() -> None:
    df = pd.DataFrame(
        [
            {"sample_id": "a", "passed": True, "attempts": 1},
            {"sample_id": "b", "passed": True, "attempts": 3},
            {"sample_id": "c", "passed": False, "attempts": 3},
        ]
    )
    assert one_shot_pass_rate(df) == 1 / 3  # only 'a' solved first try
    assert METRICS["multi_shot_pass_rate"](df) == 2 / 3


def test_to_bool_handles_native_types() -> None:
    from qabench.scoring.metrics import _to_bool

    assert _to_bool(True) == 1.0
    assert _to_bool(False) == 0.0
    assert _to_bool(1) == 1.0
    assert math.isnan(_to_bool(None))
    assert math.isnan(_to_bool(float("nan")))


def test_composite_and_tier() -> None:
    df = _unit_frame()
    score = composite(df)
    assert 0.0 <= score <= 1.0
    assert tier(0.9) == "A"
    assert tier(0.65) == "B"
    assert tier(0.3) == "C"
    assert tier(float("nan")) == "n/a"


def test_bool_metric_excludes_missing_rows() -> None:
    # Rows from a track that doesn't emit the field (NaN) must not count as True.
    from qabench.scoring.metrics import hallucination_rate, localization_accuracy

    df = pd.DataFrame(
        [
            {"hallucinated": False, "localized": float("nan")},  # unit-test row
            {"hallucinated": float("nan"), "localized": True},  # bug-loc row
            {"hallucinated": float("nan"), "localized": float("nan")},  # e2e row
        ]
    )
    assert hallucination_rate(df) == 0.0  # only the one real (False) row counts
    assert localization_accuracy(df) == 1.0  # only the one real (True) row counts


def test_pattern_adoption_and_composite() -> None:
    from qabench.scoring.metrics import composite, pattern_adoption

    df = pd.DataFrame(
        [
            {"passed": True, "pattern_used": True, "design_judge": 0.8},
            {"passed": True, "pattern_used": False, "design_judge": 0.6},
        ]
    )
    assert pattern_adoption(df) == 0.5
    score = composite(df)  # uses passed + pattern_adoption + design
    assert 0.0 < score < 1.0


def test_craft_and_review_scores_and_composite() -> None:
    from qabench.scoring.metrics import composite, craft_score, review_score

    df = pd.DataFrame(
        [
            {
                "passed": True,
                "pattern_used": 1.0,
                "locator_quality": 0.9,
                "assertion_quality": 1.0,
                "waiting_quality": 1.0,
                "teardown_hygiene": float("nan"),
                "uses_hardcoded_url": False,
                "has_code_smell": False,
                "review_score": 0.6,
            },
            {
                "passed": False,
                "pattern_used": 0.5,
                "locator_quality": 0.7,
                "assertion_quality": 0.0,
                "waiting_quality": 0.5,
                "teardown_hygiene": float("nan"),
                "uses_hardcoded_url": True,
                "has_code_smell": True,
                "review_score": 0.4,
            },
        ]
    )
    # craft_score blends positive facets with inverse smell rates; stays in [0,1].
    cs = craft_score(df)
    assert 0.0 < cs < 1.0
    assert review_score(df) == 0.5
    # composite uses them and stays bounded.
    score = composite(df)
    assert 0.0 < score < 1.0


def test_cost_per_correct() -> None:
    from qabench.scoring.metrics import cost_per_correct

    df = pd.DataFrame(
        [
            {"cost": 0.10, "passed": True},
            {"cost": 0.10, "passed": True},
            {"cost": 0.10, "passed": False},
        ]
    )
    assert math.isclose(cost_per_correct(df), 0.15)  # $0.30 spent / 2 passing


def test_cost_per_correct_nan_when_none_pass() -> None:
    from qabench.scoring.metrics import cost_per_correct

    df = pd.DataFrame([{"cost": 0.10, "passed": False}])
    assert math.isnan(cost_per_correct(df))


def test_aggregate_averages_over_trials_and_reports_std() -> None:
    from qabench.aggregate import summarize

    # Two trials of one unit-test sample: trial 0 kills all mutants, trial 1 none.
    rows = []
    for trial, surviving in [(0, 0), (1, 4)]:
        rows.append(
            {
                "model_slug": "m",
                "track": "unit_test_gen",
                "sample_id": "s",
                "trial": trial,
                "tests_total": 5,
                "tests_failing_on_correct": 0,
                "mutants_total": 4,
                "mutants_surviving": surviving,
                "mutants_killed": 4 - surviving,
                "coverage_pct": 100.0,
                "runs_and_valid": True,
                "passed": True,
                "attempts": 1,
                "design_judge": 0.8,
                "hallucinated": False,
            }
        )
    summary = summarize(pd.DataFrame(rows))
    row = summary[summary["track"] == "unit_test_gen"].iloc[0]
    # recall pooled over both trials = killed(4+0) / total(4+4) = 0.5
    assert row["recall"] == 0.5
    assert row["n_trials"] == 2
    assert row["composite_std"] > 0  # the two trials genuinely differ


def test_overall_composite_averages_execution_tracks_only() -> None:
    from qabench.aggregate import summarize
    from qabench.scoring.metrics import composite

    df = pd.DataFrame(
        [
            {
                "model_slug": "m",
                "track": "unit_test_gen",
                "sample_id": "u",
                "trial": 0,
                "tests_total": 5,
                "tests_failing_on_correct": 0,
                "mutants_total": 4,
                "mutants_surviving": 0,
                "mutants_killed": 4,
                "coverage_pct": 100.0,
                "runs_and_valid": True,
                "passed": True,
                "attempts": 1,
                "design_judge": 0.8,
                "hallucinated": False,
            },
            {
                "model_slug": "m",
                "track": "bug_localization",
                "sample_id": "b",
                "trial": 0,
                "localized": True,
                "passed": True,
                "attempts": 1,
            },
            # Judge-only track with a deliberately low score — must be excluded.
            {
                "model_slug": "m",
                "track": "test_case_design",
                "sample_id": "t",
                "trial": 0,
                "design_judge": 0.0,
            },
        ]
    )
    summary = summarize(df)
    all_row = summary[summary["track"] == "ALL"].iloc[0]
    exp_unit = composite(df[df["track"] == "unit_test_gen"])
    exp_bug = composite(df[df["track"] == "bug_localization"])
    expected = (exp_unit + exp_bug) / 2
    assert math.isclose(float(all_row["composite"]), round(expected, 4), abs_tol=1e-4)
    # The judge-only track's 0.0 composite does not drag the headline down.
    per_track = summary.set_index("track")["composite"]
    assert float(per_track["test_case_design"]) == 0.0
    assert float(all_row["composite"]) > 0.9


def test_registry_is_complete() -> None:
    expected = {"false_positive_rate", "false_negative_rate", "precision", "recall", "f1"}
    assert expected <= set(METRICS)
