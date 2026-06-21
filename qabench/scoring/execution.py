"""Execution-based scoring for the unit-test-generation track (Python).

A small self-contained harness is dropped into the sandbox. It (1) runs the
model's tests against the correct module for validity + coverage, then (2) applies
each stored mutant and reruns to measure the mutation-kill rate. The harness prints
one JSON blob after a marker, which we parse back here.

False positives / false negatives fall out of this directly:
- a test that FAILS on the correct module is a false positive (false alarm),
- a mutant that SURVIVES the suite is a false negative (missed bug).
"""

from __future__ import annotations

import json

from qabench.types import ExecResult, Sample, ScoreContext, ScoreRow

RESULT_MARKER = "===QABENCH-RESULT==="

_HARNESS = """
import json, re, subprocess, sys

spec = json.load(open("_spec.json"))
module_file = spec["module_file"]
module_name = spec["module_name"]
test_file = spec["test_file"]
mutants = spec["mutant_files"]


def run_pytest(coverage):
    cmd = [sys.executable, "-m"]
    if coverage:
        cmd += ["coverage", "run", "--source", module_name, "-m", "pytest"]
    else:
        cmd += ["pytest"]
    cmd += [test_file, "-q", "-p", "no:cacheprovider", "--tb=no", "-o", "addopts="]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    return proc.returncode, proc.stdout + proc.stderr


def count(word, text):
    m = re.search(r"(\\d+) " + word, text)
    return int(m.group(1)) if m else 0


correct_src = open(module_file).read()

rc, out = run_pytest(coverage=True)
passed = count("passed", out)
failed = count("failed", out)
errors = count("error", out) + count("errors", out)
total = passed + failed + errors

coverage_pct = None
try:
    subprocess.run([sys.executable, "-m", "coverage", "json", "-o", "cov.json", "-q"],
                   capture_output=True, text=True)
    coverage_pct = json.load(open("cov.json"))["totals"]["percent_covered"]
except Exception:
    pass

# pytest exit codes: 0 ok, 1 failures, 2 usage/collection error, 5 no tests.
collection_ok = rc not in (2, 5) and total > 0

killed = 0
for mf in mutants:
    open(module_file, "w").write(open(mf).read())
    rc_m, _ = run_pytest(coverage=False)
    if rc_m != 0:
        killed += 1
    open(module_file, "w").write(correct_src)

result = {
    "tests_total": total,
    "tests_passed": passed,
    "tests_failing_on_correct": failed + errors,
    "collection_ok": collection_ok,
    "coverage_pct": coverage_pct,
    "mutants_total": len(mutants),
    "mutants_killed": killed,
}
print("===QABENCH-RESULT===")
print(json.dumps(result))
"""


def _build_files(sample: Sample, tests: str) -> dict[str, str]:
    payload = sample.payload
    module_file = f"{payload['module_name']}.py"
    mutants: list[str] = list(payload.get("mutants", []))
    files = {
        module_file: str(payload["source"]),
        "test_gen.py": tests,
        "_runner.py": _HARNESS,
        "_spec.json": json.dumps(
            {
                "module_file": module_file,
                "module_name": payload["module_name"],
                "test_file": "test_gen.py",
                "mutant_files": [f"_mut_{i}.py" for i in range(len(mutants))],
            }
        ),
    }
    for i, mut in enumerate(mutants):
        files[f"_mut_{i}.py"] = mut
    return files


def _as_int(value: object) -> int:
    """Coerce a JSON value to int, defaulting to 0."""
    return int(value) if isinstance(value, int | float) else 0


def _parse(res: ExecResult) -> dict[str, object]:
    if RESULT_MARKER not in res.stdout:
        return {}
    blob = res.stdout.split(RESULT_MARKER, 1)[1].strip()
    try:
        data: dict[str, object] = json.loads(blob.splitlines()[0])
        return data
    except (json.JSONDecodeError, IndexError):
        return {}


def score_unit_tests(sample: Sample, parsed: str, ctx: ScoreContext) -> ScoreRow:
    """Run the model's tests; return validity, coverage, and mutation fields."""
    from qabench.sandbox import PYTHON_IMAGE

    files = _build_files(sample, parsed)
    res = ctx.sandbox.run(
        image=PYTHON_IMAGE,
        files=files,
        command=["python", "_runner.py"],
        timeout_s=180,
    )
    data = _parse(res)
    if not data:
        return {
            "exec_ok": False,
            "tests_total": 0,
            "tests_failing_on_correct": 0,
            "mutants_total": len(sample.payload.get("mutants", [])),
            "mutants_surviving": len(sample.payload.get("mutants", [])),
            "coverage_pct": 0.0,
            "runs_and_valid": False,
            "passed": False,
            "exec_error": (res.stderr or res.stdout)[-500:],
        }

    total = _as_int(data.get("tests_total"))
    failing = _as_int(data.get("tests_failing_on_correct"))
    collection_ok = bool(data.get("collection_ok", False))
    mut_total = _as_int(data.get("mutants_total"))
    mut_killed = _as_int(data.get("mutants_killed"))
    cov = data.get("coverage_pct")
    coverage = float(cov) if isinstance(cov, int | float) else 0.0
    runs_and_valid = collection_ok and failing == 0 and total > 0

    return {
        "exec_ok": True,
        "tests_total": total,
        "tests_failing_on_correct": failing,
        "mutants_total": mut_total,
        "mutants_killed": mut_killed,
        "mutants_surviving": mut_total - mut_killed,
        "coverage_pct": coverage,
        "runs_and_valid": runs_and_valid,
        "passed": runs_and_valid,
    }


def unit_test_feedback(sample: Sample, parsed: str, ctx: ScoreContext) -> tuple[bool, str]:
    """Multi-shot feedback: did the suite run+pass on the correct module?"""
    row = score_unit_tests(sample, parsed, ctx)
    passed = bool(row.get("passed"))
    if passed:
        return True, ""
    if not row.get("exec_ok"):
        return False, f"The test suite failed to run:\n{row.get('exec_error', '')}"
    failing = row.get("tests_failing_on_correct", 0)
    return False, (
        f"{failing} of your tests fail against the correct implementation. "
        "Your tests must pass on correct code. Fix the assertions/imports."
    )
