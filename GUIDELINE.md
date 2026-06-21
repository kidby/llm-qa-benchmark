# Evaluation Tracks and Task Contracts

Each track defines its input, the expected model output, and a scoring methodology. Datasets live in
`datasets/<track>/<sample_id>/`.

## `unit_test_gen`: Unit Test Generation

**Input.** A single source module, `source.py`, and its module name.

**Output.** A test suite in one fenced code block, such as `pytest` for Python.

**Dataset structure.**

```
datasets/unit_test_gen/<id>/
├── meta.json      # { "module_name": "...", "language": "python" }
├── source.py      # The correct reference implementation
└── mutants/       # Complete replacement modules with injected faults
```

**Metrics.**

- **Execution validity.** The suite must run and pass against the reference implementation. A test
  that fails here is a false positive.
- **Mutation score.** The suite is run against each injected fault. A mutant is killed when the
  suite fails on it; a surviving mutant is a false negative.
- **Code coverage.** Line and branch coverage computed with `coverage.py`.
- **Static analysis.** Validates syntax, the presence of assertions, and sandbox safety.
- **Hallucination check.** An LLM verifies that the suite invokes no non-existent symbols.

## `bug_localization`: Bug Detection and Localization

**Input.** A target module annotated with line numbers and a reported symptom.

**Output.** A JSON object describing the fault location, root cause, and proposed fix:
`{ "line": <int>, "root_cause": "...", "proposed_fix": "..." }`.

**Dataset structure.**

```
datasets/bug_localization/<id>/
├── meta.json        # { "module_name", "fault_lines": [..], "symptom": "..." }
├── buggy.py         # The module containing a single fault
└── test_hidden.py   # Optional test that passes only once the bug is resolved
```

**Metrics.**

- **Localization accuracy.** The predicted `start_line`–`end_line` span must cover `fault_lines`,
  exactly or within a ±1 line tolerance. A single-line answer sets `end_line` equal to `start_line`.
- **Repair execution.** When a hidden test is provided, the proposed fix replaces the predicted line
  span and the test is run to validate it.
- **LLM judge.** Qualitative scoring of the root-cause explanation.

## `test_case_design`: Test Case Design

**Input.** A natural-language system or feature requirement.

**Output.** A JSON array of test cases, each with `id`, `title`, `category`, `preconditions`,
`steps`, `input`, and `expected`.

**Dataset structure.**

```
datasets/test_case_design/<id>/
├── requirement.md          # The natural-language specification
└── reference_classes.json  # Reference equivalence classes and boundary values
```

**Metrics.**

- **LLM judge.** Scores the suite from 0.0 to 1.0 on equivalence-partition coverage, boundary-value
  analysis, negative and error-case handling, and concreteness. No code is executed in this track,
  so it is reported on its own and excluded from the headline composite, which averages only the
  execution-grounded tracks.

## `e2e_ui`: End-to-End UI Automation

**Input.** A user-flow narrative, a base URL, and a defined success condition.

**Output.** A self-contained Playwright test script in TypeScript.

**Dataset structure.**

```
datasets/e2e_ui/<id>/
├── meta.json   # { "base_url": "...", "success_assertion": "..." }
└── flow.md     # The user-flow description
```

**Metrics.**

- **Execution verification.** The script runs inside a Playwright container against the local sample
  application in `docker/webapp/`, scored on pass or fail.
- **Selector robustness.** Static analysis rewards resilient locators such as `getByRole`,
  `getByText`, and `getByTestId`, and penalizes brittle ones such as exact DOM paths, `nth-child`,
  and raw XPath.

## `e2e_advanced`: Advanced E2E Patterns

**Input.** A scenario narrative, a base URL, and a success condition. The scenario *implies* a
Playwright technique but never names it.

**Output.** A self-contained Playwright test script in TypeScript.

**Dataset structure.**

```
datasets/e2e_advanced/<id>/
├── meta.json   # { "base_url", "success_assertion", "expected_pattern" }
└── flow.md     # The scenario; wording implies the technique without naming it
```

`expected_pattern` is one of `structure`, `fixtures`, `polling`, `network`, `api`, `download`,
`accessibility`, `performance`, or `realtime`. It drives scoring only and is never placed in the
prompt. `structure` is pattern-agnostic: any reusable structure satisfies it (page object model,
page-object-component, screenplay, or clean page-helper decomposition) — no single pattern is
mandated or disallowed.

**Metrics.**

- **Execution verification.** The script runs inside the Playwright container against the richer app
  in `docker/advanced-app/` (port 8081), scored on pass or fail.
- **Pattern adoption.** Static detection of whether the model applied the implicitly-required
  technique (`pattern_used`), graded 1.0/0.5/0.0 — a proper tool earns full credit, a weaker-but-
  valid form earns half. Tested against the app surface built to call for it.
- **Craft checks.** Deterministic static signals — locator quality, web-first vs. manual
  assertions, waiting quality, hardcoded URLs, code smells — validated against a human golden set.
- **Review judge.** A structured LLM craft review, included at a low weight (it agreed only weakly
  with human labels on the golden set) and never overriding execution.

Mobile automation (Appium) is intentionally out of scope: the web-execution sandbox cannot run a
device emulator, and detection-only scoring would break the execution-based principle.

## `e2e_repair`: Fix a Failing Playwright Test

**Input.** A failing Playwright test, the runner output it produced (error, call log, code frame),
a base URL, and the success condition. The application is correct; the fault is in the test.

**Output.** A corrected Playwright test in TypeScript.

**Dataset structure.**

```
datasets/e2e_repair/<id>/
├── broken.spec.ts   # The failing test
├── error.txt        # Playwright runner output (the artifact pasted into an assistant)
└── meta.json        # { "base_url", "success_assertion", optional "expected_pattern" }
```

**Metrics.**

- **Execution verification.** The corrected test runs against `docker/advanced-app/` and is scored
  on whether it now passes.
- **Structure preservation.** When the broken test already uses a structural pattern
  (`expected_pattern`), the fix is checked for keeping it rather than flattening to inline code.
- **Craft + review judge.** The same deterministic craft checks and low-weight structured review
  judge as the other E2E tracks.

## Extending Datasets

To add a sample, create a new `<id>/` directory under the relevant track with the required files.
The loader discovers and registers it automatically. Keep every sample small, deterministic, and
dependency-free to guarantee consistent, isolated execution across environments.
