from __future__ import annotations

from qabench.llm import make_fake
from qabench.sandbox import LocalSandbox
from qabench.scoring.context import Context
from qabench.scoring.execution import score_unit_tests
from qabench.scoring.localization import score_localization
from qabench.scoring.static_checks import score_selector_robustness, score_static_tests
from qabench.tracks import TRACKS
from qabench.types import Sample


def _ctx() -> Context:
    return Context(
        sandbox=LocalSandbox(),
        judge=make_fake('{"score": 0.5, "rationale": "x", "hallucinated": false}'),
        judge_model_id="judge",
    )


def _fizzbuzz_sample() -> Sample:
    return next(s for s in TRACKS["unit_test_gen"].load_dataset() if s.id == "fizzbuzz")


def _num(value: object) -> float:
    assert isinstance(value, int | float) and not isinstance(value, bool)
    return float(value)


GOOD_SUITE = (
    "from fizzbuzz import fizzbuzz\n"
    "import pytest\n"
    "def test_all():\n"
    "    assert fizzbuzz(3) == 'Fizz'\n"
    "    assert fizzbuzz(5) == 'Buzz'\n"
    "    assert fizzbuzz(15) == 'FizzBuzz'\n"
    "    assert fizzbuzz(1) == '1'\n"
    "def test_validation():\n"
    "    with pytest.raises(ValueError):\n"
    "        fizzbuzz(0)\n"
)

# A suite that asserts something false: it fails on the CORRECT module.
FALSE_ALARM_SUITE = (
    "from fizzbuzz import fizzbuzz\ndef test_wrong():\n    assert fizzbuzz(3) == 'Buzz'\n"
)


def test_good_suite_kills_mutants_no_false_positive() -> None:
    row = score_unit_tests(_fizzbuzz_sample(), GOOD_SUITE, _ctx())
    assert row["exec_ok"] is True
    assert row["runs_and_valid"] is True
    assert row["tests_failing_on_correct"] == 0
    assert row["mutants_surviving"] == 0  # all injected bugs caught
    assert _num(row["coverage_pct"]) > 50


def test_false_alarm_suite_flagged_as_false_positive() -> None:
    row = score_unit_tests(_fizzbuzz_sample(), FALSE_ALARM_SUITE, _ctx())
    assert _num(row["tests_failing_on_correct"]) >= 1
    assert row["runs_and_valid"] is False
    assert row["passed"] is False


def test_localization_correct_line_and_repair() -> None:
    sample = next(s for s in TRACKS["bug_localization"].load_dataset() if s.id == "binary_search")
    parsed = {"line": 9, "proposed_fix": "    while lo <= hi:", "root_cause": "bound"}
    row = score_localization(sample, parsed, _ctx())
    assert row["localized"] is True
    assert row["repair_attempted"] is True
    assert row["repair_passed"] is True


def test_localization_wrong_line() -> None:
    sample = next(s for s in TRACKS["bug_localization"].load_dataset() if s.id == "binary_search")
    row = score_localization(sample, {"line": 1}, _ctx())
    assert row["localized"] is False


def test_localization_multiline_span_covers_fault() -> None:
    sample = next(s for s in TRACKS["bug_localization"].load_dataset() if s.id == "binary_search")
    # A span that brackets the known fault line (9) localizes it.
    parsed = {"start_line": 8, "end_line": 10, "root_cause": "bound"}
    row = score_localization(sample, parsed, _ctx())
    assert row["localized"] is True
    assert row["localized_within_1"] is True
    assert row["predicted_line"] == 8
    assert row["predicted_end_line"] == 10


def test_e2e_patterns_ignore_comments_and_strings() -> None:
    from qabench.scoring.static_checks import score_e2e_patterns

    # The technique is only named in a comment and a string literal — not used.
    code = (
        "// this test could use page.route to abort the request\n"
        "const note = 'remember to await request.post next time';\n"
        "await page.getByRole('button').click();\n"
    )
    sample = Sample(id="s", track="e2e_advanced", payload={"expected_pattern": "network"})
    row = score_e2e_patterns(sample, code, _ctx())
    assert row["uses_network"] is False
    assert row["uses_api"] is False
    assert row["pattern_used"] == 0.0


def test_page_object_detected_by_structure_not_name() -> None:
    from qabench.scoring.static_checks import score_e2e_patterns

    sample = Sample(id="s", track="e2e_advanced", payload={"expected_pattern": "page_object"})
    # Differently-named wrapper that holds a Page is a page object.
    wrapper = (
        "class LoginScreen {\n"
        "  constructor(private readonly page: Page) {}\n"
        "  async login() { await this.page.goto('/'); }\n"
        "}\n"
    )
    assert score_e2e_patterns(sample, wrapper, _ctx())["uses_page_object"] is True
    # A plain data class is not a page object.
    model = "class UserModel { name: string; email: string; }\n"
    assert score_e2e_patterns(sample, model, _ctx())["uses_page_object"] is False


def test_structure_is_pattern_agnostic() -> None:
    from qabench.scoring.static_checks import score_e2e_patterns

    sample = Sample(id="s", track="e2e_advanced", payload={"expected_pattern": "structure"})
    # Helper-function decomposition (no class) is valid reusable structure.
    helpers = (
        "async function signIn(page, user, pw) {\n"
        "  await page.getByLabel(/username/i).fill(user);\n"
        "}\n"
        "test('t', async ({ page }) => { await signIn(page, 'demo', 'pw'); });\n"
    )
    row = score_e2e_patterns(sample, helpers, _ctx())
    assert row["uses_structure"] is True
    assert row["pattern_used"] == 1.0
    # The screenplay pattern also counts as structure.
    screenplay = "await actor.attemptsTo(Login.withCredentials('demo', 'pw'));\n"
    assert score_e2e_patterns(sample, screenplay, _ctx())["uses_structure"] is True
    # A flat inline test with no decomposition is not structured.
    flat = "test('t', async ({ page }) => { await page.goto('/'); });\n"
    assert score_e2e_patterns(sample, flat, _ctx())["uses_structure"] is False


def test_selector_robustness_ignores_commented_brittle_locator() -> None:
    sample = TRACKS["e2e_ui"].load_dataset()[0]
    code = (
        "// old: await page.locator('div:nth-child(3)').click();\n"
        "await page.getByRole('button').click();\n"
    )
    assert score_selector_robustness(sample, code, _ctx())["selectors_robust"] is True


def test_static_checks() -> None:
    sample = _fizzbuzz_sample()
    row = score_static_tests(sample, GOOD_SUITE, _ctx())
    assert row["static_parses"] is True
    assert row["static_has_assert"] is True
    assert row["static_no_network"] is True


def test_e2e_patterns_detect_and_match() -> None:
    from qabench.scoring.static_checks import score_e2e_patterns

    snippets = {
        "page_object": "class LoginPage { constructor(page) {} }",
        "fixtures": "const test = base.extend({ user: async ({}, use) => {} });",
        "network": "await page.route('**/api/todos', r => r.abort());",
        "polling": "await expect.poll(() => x).toBe(1);",
        "api": "const res = await request.post('/api/todos');",
    }
    for expected, code in snippets.items():
        sample = Sample(id="s", track="e2e_advanced", payload={"expected_pattern": expected})
        row = score_e2e_patterns(sample, code, _ctx())
        assert row[f"uses_{expected}"] is True
        assert row["pattern_used"] == 1.0


def test_pattern_strength_graded_polling_and_fixtures() -> None:
    from qabench.scoring.static_checks import score_e2e_patterns

    poll = Sample(id="s", track="e2e_advanced", payload={"expected_pattern": "polling"})
    # Dedicated poll API → full credit.
    proper = "await expect.poll(() => status()).toBe('done');"
    assert score_e2e_patterns(poll, proper, _ctx())["pattern_used"] == 1.0
    # Web-first assertion with a timeout → partial (works, but not the proper tool).
    fallback = "await expect(page.getByTestId('s')).toHaveText('done', { timeout: 30000 });"
    assert score_e2e_patterns(poll, fallback, _ctx())["pattern_used"] == 0.5

    fix = Sample(id="s", track="e2e_advanced", payload={"expected_pattern": "fixtures"})
    # Custom fixture / setup-project → full; manual shared hook → partial.
    assert score_e2e_patterns(fix, "const test = base.extend({});", _ctx())["pattern_used"] == 1.0
    hook = "test.beforeAll(async ({ browser }) => {}); test.use({ storageState: 'a.json' });"
    assert score_e2e_patterns(fix, hook, _ctx())["pattern_used"] == 0.5


def test_e2e_patterns_detect_modern_techniques() -> None:
    from qabench.scoring.static_checks import score_e2e_patterns

    snippets = {
        "download": "const dl = await page.waitForEvent('download'); await dl.path();",
        "accessibility": (
            "import { AxeBuilder } from '@axe-core/playwright';\n"
            "const r = await new AxeBuilder({ page }).analyze();"
        ),
        "performance": (
            "const nav = await page.evaluate(() => performance.getEntriesByType('navigation'));"
        ),
        "realtime": (
            "await page.routeWebSocket('ws://localhost:8081/feed', ws => "
            "ws.send(JSON.stringify({ unread: 3 })));"
        ),
    }
    for expected, code in snippets.items():
        sample = Sample(id="s", track="e2e_advanced", payload={"expected_pattern": expected})
        row = score_e2e_patterns(sample, code, _ctx())
        assert row[f"uses_{expected}"] is True
        assert row["pattern_used"] == 1.0


def test_e2e_patterns_wrong_technique_not_credited() -> None:
    from qabench.scoring.static_checks import score_e2e_patterns

    # A plain UI test does not satisfy a scenario that wanted network interception.
    sample = Sample(id="s", track="e2e_advanced", payload={"expected_pattern": "network"})
    row = score_e2e_patterns(sample, "await page.getByRole('button').click();", _ctx())
    assert row["pattern_used"] == 0.0


def test_craft_rewards_modern_practice() -> None:
    from qabench.scoring.static_checks import score_craft

    sample = Sample(id="s", track="e2e_advanced", payload={})
    good = (
        "test('t', async ({ page, request }) => {\n"
        "  const res = await request.post('/api/todos', { data: { title: `t-${Date.now()}` } });\n"
        "  await expect(res).toBeOK();\n"
        "  await expect(page.getByRole('listitem')).toHaveCount(2);\n"
        "});\n"
    )
    g = score_craft(sample, good, _ctx())
    assert g["assertion_quality"] == 1.0
    assert g["uses_unique_data"] is True
    assert g["uses_hardcoded_url"] is False
    assert g["has_code_smell"] is False

    bad = (
        "test('t', async ({ page }) => {\n"
        "  await page.goto('http://localhost:8081/app');\n"
        "  await page.waitForTimeout(3000);\n"
        "  const n = await page.evaluate(() => document.querySelectorAll('li').length);\n"
        "  expect(await page.locator('div:nth-child(2)').isVisible()).toBe(true);\n"
        "});\n"
    )
    b = score_craft(sample, bad, _ctx())
    assert b["uses_hardcoded_url"] is True
    assert b["uses_arbitrary_timeout"] is True
    assert b["waiting_quality"] == 0.0
    assert b["has_code_smell"] is True
    assert b["uses_fragile_selector"] is True


def test_selector_robustness() -> None:
    sample = TRACKS["e2e_ui"].load_dataset()[0]
    robust = "await page.getByRole('button').click();"
    brittle = "await page.locator('div:nth-child(3)').click();"
    assert score_selector_robustness(sample, robust, _ctx())["selectors_robust"] is True
    assert score_selector_robustness(sample, brittle, _ctx())["selectors_robust"] is False
