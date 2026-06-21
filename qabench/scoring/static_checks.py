"""Cheap static checks — no execution. Parse, assertions present, no I/O escape."""

from __future__ import annotations

import ast
import re
from collections.abc import Callable

from qabench.types import Sample, ScoreContext, ScoreRow

_FORBIDDEN = re.compile(r"\b(socket|requests|urllib|httpx|subprocess)\b")
_BRITTLE_SELECTOR = re.compile(r"nth-child|//\w+\[|xpath=", re.IGNORECASE)

# Comments and string/template literals, matched in a SINGLE left-to-right pass so
# that a ``//`` inside a string (e.g. an ``http://`` URL) is consumed as part of the
# string rather than mistaken for a line comment. Best-effort: regex literals and
# nested template expressions are not modelled.
_TOKEN = re.compile(
    r"(?P<str>\"(?:\\.|[^\"\\])*\"|'(?:\\.|[^'\\])*'|`(?:\\.|[^`\\])*`)"
    r"|(?P<comment>//[^\n]*|/\*.*?\*/)",
    re.DOTALL,
)


def _strip_comments(code: str) -> str:
    """Remove JS/TS comments only, keeping string literals (where selectors live)."""
    return _TOKEN.sub(lambda m: " " if m.lastgroup == "comment" else m.group(0), code)


def _strip_js_noise(code: str) -> str:
    """Remove comments and string/template literals for token-level detection."""
    return _TOKEN.sub(" ", code)


def score_static_tests(sample: Sample, parsed: str, ctx: ScoreContext) -> ScoreRow:
    """Static quality signals for a generated test file."""
    del ctx  # static checks do not execute anything
    code = parsed if isinstance(parsed, str) else str(parsed)
    parses = _parses(code, sample.language)
    has_assert = bool(re.search(r"\bassert\b|expect\s*\(", code))
    no_network = not _FORBIDDEN.search(code)
    return {
        "static_parses": parses,
        "static_has_assert": has_assert,
        "static_no_network": no_network,
    }


def score_selector_robustness(sample: Sample, parsed: str, ctx: ScoreContext) -> ScoreRow:
    """Penalise brittle locators in E2E scripts; reward role/text/testid usage."""
    del sample, ctx
    code = parsed if isinstance(parsed, str) else str(parsed)
    # Selectors live inside string literals, so strip comments only — stripping
    # strings would erase the very locators we are inspecting.
    scan = _strip_comments(code)
    robust = bool(re.search(r"getByRole|getByLabel|getByText|getByTestId|data-testid", scan))
    brittle = bool(_BRITTLE_SELECTOR.search(scan))
    return {"selectors_robust": robust and not brittle}


def _detector(pattern: str) -> Callable[[str], bool]:
    compiled = re.compile(pattern)
    return lambda code: bool(compiled.search(code))


# A page object is a class that *wraps* a Playwright Page — detected structurally
# rather than by name, so a differently-named wrapper (LoginScreen) counts while
# an unrelated data class (UserModel) does not.
_PO_CLASS = re.compile(r"\bclass\s+\w+")
_PO_NAMED = re.compile(r"\bclass\s+\w*Page\b")
_PO_WRAPS_PAGE = re.compile(r":\s*Page\b|\bthis\.page\b")


def _detect_page_object(code: str) -> bool:
    if _PO_NAMED.search(code):
        return True
    return bool(_PO_CLASS.search(code) and _PO_WRAPS_PAGE.search(code))


# Structure is pattern-agnostic: any sound way of imposing reusable structure on the
# test counts — page object model, page-object-component, the screenplay pattern, or
# clean helper-function decomposition. No single pattern is mandated or disallowed.
_HELPER_FN = re.compile(r"(?:async\s+)?function\s+\w+\s*\([^)]*\bpage\b")
_HELPER_ARROW = re.compile(r"\bconst\s+\w+\s*=\s*(?:async\s*)?\([^)]*\bpage\b[^)]*\)\s*=>")
_SCREENPLAY = re.compile(
    r"\bactor\b|attemptsTo\s*\(|\bActor\b|\bTask\b|\bAbility\b|answeredBy\s*\(|\bperformAs\b"
)


def _detect_structure(code: str) -> bool:
    """Any reusable structure: page object, component, screenplay, or page helpers."""
    return bool(
        _detect_page_object(code)
        or _HELPER_FN.search(code)
        or _HELPER_ARROW.search(code)
        or _SCREENPLAY.search(code)
    )


# Detectors for advanced Playwright techniques. The model is never told which to
# use; these check whether it discovered the right one for the scenario. All run
# on comment/string-stripped code so a mention in prose never counts as usage.
_PATTERN_DETECTORS: dict[str, Callable[[str], bool]] = {
    # ``structure`` is the inclusive, scored signal (any reusable structure);
    # ``page_object`` is kept as a finer-grained diagnostic of one specific form.
    "structure": _detect_structure,
    "page_object": _detect_page_object,
    # Shared-setup reuse is pattern-agnostic too: custom fixtures (``test.extend``),
    # the recommended setup-project + ``storageState`` auth reuse, or a shared hook.
    "fixtures": _detector(
        r"\b(test|base)\.extend\s*\(|storageState|dependencies\s*:\s*\[|\bbeforeAll\s*\("
    ),
    "network": _detector(r"\.route\s*\(|route\.(abort|fulfill|continue)\s*\("),
    # Polling means waiting for async state via an auto-retrying mechanism — the
    # explicit poll APIs OR a web-first assertion (the recommended way), NOT a
    # one-shot snapshot read. (See the e2e quality rubric.)
    "polling": _detector(
        r"expect\.poll\s*\(|\.toPass\s*\(|waitForFunction|waitForResponse|waitForRequest"
        r"|waitForURL|waitForLoadState"
        r"|\.to(HaveText|ContainText|BeVisible|BeHidden|HaveValue|HaveCount|BeEnabled|HaveURL)\s*\("
    ),
    "api": _detector(r"\brequest\.(get|post|put|delete|fetch)\s*\(|APIRequestContext|\.request\b"),
    "download": _detector(
        r"waitForEvent\s*\(\s*['\"]download['\"]|\.suggestedFilename\b"
        r"|download\.(path|saveAs|createReadStream)\s*\(|\.on\s*\(\s*['\"]download['\"]"
    ),
    "accessibility": _detector(
        r"\bAxeBuilder\b|@axe-core/playwright|\baxe\.run\s*\(|\.accessibility\.snapshot\s*\("
    ),
    "performance": _detector(
        r"performance\.(getEntries|getEntriesByType|timing|now)\b"
        r"|PerformanceObserver|web-vitals|lighthouse"
    ),
    "realtime": _detector(
        r"routeWebSocket\s*\(|\bWebSocketRoute\b|createCDPSession\s*\(|\bCDPSession\b"
    ),
}

# Detectors whose signal lives in a string argument (e.g. the ``'download'`` event
# name) must see string literals, so they run on comment-stripped code rather than
# the fully-stripped code the token detectors use.
_STRING_SENSITIVE = {"download"}

# Some techniques have a clear "proper tool" vs "acceptable but weaker" gradation,
# so ``pattern_used`` is scored 1.0 / 0.5 / 0.0 rather than purely binary:
#   polling  — dedicated poll APIs (full) vs a web-first assertion fallback (partial)
#   fixtures — custom fixture / setup-project (full) vs a manual shared hook (partial)
_POLLING_PROPER = re.compile(
    r"expect\.poll\s*\(|\.toPass\s*\(|waitForFunction|waitForResponse|waitForRequest"
)
# A custom fixture or setup project is the strong form; building shared state by hand
# in a beforeAll/beforeEach hook is the weaker form; reusing saved storageState is fine.
_FIXTURES_STRONG = re.compile(r"\b(test|base)\.extend\s*\(|dependencies\s*:\s*\[")
_FIXTURES_HOOK = re.compile(r"\bbeforeAll\s*\(|\bbeforeEach\s*\(")
_FIXTURES_STATE = re.compile(r"storageState")


def _pattern_strength(expected: str, scan: str, attempted: bool) -> float:
    """Graded credit for the expected technique: 1.0 full, 0.5 partial, 0.0 none."""
    if not attempted:
        return 0.0
    if expected == "polling":
        # Dedicated poll APIs are full credit; a web-first assertion is the weaker fallback.
        return 1.0 if _POLLING_PROPER.search(scan) else 0.5
    if expected == "fixtures":
        if _FIXTURES_STRONG.search(scan):
            return 1.0  # custom fixture or setup project
        if _FIXTURES_HOOK.search(scan):
            return 0.5  # manual shared state in a hook
        return 1.0 if _FIXTURES_STATE.search(scan) else 0.0  # clean storageState reuse
    return 1.0


def score_e2e_patterns(sample: Sample, parsed: str, ctx: ScoreContext) -> ScoreRow:
    """Detect advanced Playwright techniques and whether the expected one was used.

    ``pattern_used`` is the headline signal: did the model apply the technique the
    scenario implicitly calls for (``sample.payload['expected_pattern']``)?
    """
    del ctx
    code = parsed if isinstance(parsed, str) else str(parsed)
    scan_full = _strip_js_noise(code)  # comments + strings removed (token detectors)
    scan_code = _strip_comments(code)  # strings kept (string-sensitive detectors)
    found = {
        f"uses_{name}": detect(scan_code if name in _STRING_SENSITIVE else scan_full)
        for name, detect in _PATTERN_DETECTORS.items()
    }
    expected = str(sample.payload.get("expected_pattern", ""))
    row: ScoreRow = dict(found)
    if not expected:
        # No designated technique for this sample (e.g. a plain repair task) — the
        # pattern signals are not applicable, so leave them out of the adoption metric.
        row["pattern_used"] = float("nan")
        row["pattern_attempted"] = False
        return row
    attempted = bool(found.get(f"uses_{expected}", False))
    # Graded 1.0 / 0.5 / 0.0: a proper tool earns full credit, a weaker-but-valid
    # form earns partial. ``pattern_attempted`` keeps the binary "touched it" signal.
    row["pattern_used"] = _pattern_strength(expected, scan_full, attempted)
    row["pattern_attempted"] = attempted
    return row


# --- Craft scorers (modern Playwright practice) -----------------------------
# Objective, static signals on test-automation craft, emitted by ``score_craft``.
# Reported alongside execution; NOT folded into the headline composite until each
# is validated against the human golden set. The rubric (locator/assertion/waiting/
# idempotency/url) comes from a senior SDET's review standards.

# Locator strategies ranked by resilience (Playwright's own recommended order).
_LOCATOR_TIERS: tuple[tuple[str, float], ...] = (
    (r"getByRole\s*\(", 1.0),
    (r"getByLabel\s*\(", 0.95),
    (r"getBy(Text|Placeholder|AltText|Title)\s*\(", 0.85),
    (r"getByTestId\s*\(", 0.7),
)
_CSS_LOCATOR = re.compile(r"\.locator\s*\(")

# Web-first, auto-retrying assertions (good) vs manual value extraction (weaker):
# ``expect(response).toBeOK()`` / ``expect(locator).toHaveText()`` beat
# ``expect(response.status()).toBe(200)`` or ``expect(await ...)``.
_WEBFIRST_ASSERT = re.compile(
    r"\.(toBeOK|toBeVisible|toBeHidden|toHaveText|toContainText|toHaveValue|toHaveCount"
    r"|toBeEnabled|toBeChecked|toHaveURL|toHaveAttribute|toHaveClass|toHaveTitle)\s*\("
)
_MANUAL_ASSERT = re.compile(
    r"expect\s*\(\s*await\b|\.status\s*\(\s*\)\s*\)\s*\.(toBe|toEqual)\b|\.status\s*\(\s*\)\s*[=!]=="
)

# Waiting: web-first / event-based (good) vs arbitrary fixed sleeps (bad).
_GOOD_WAIT = re.compile(
    r"waitForResponse|waitForRequest|waitForURL|waitForLoadState"
    r"|expect\.poll\s*\(|\.toPass\s*\(|\.to(BeVisible|HaveText|HaveValue|ContainText|BeEnabled)\b"
)
_ARBITRARY_WAIT = re.compile(r"waitForTimeout\s*\(|setTimeout\s*\(|\bsleep\s*\(")

# Listener/context/global setup that ought to be cleaned up, and the cleanup itself.
_NEEDS_TEARDOWN = re.compile(r"\.on\s*\(|addListener|beforeAll\s*\(|newContext\s*\(")
_HAS_TEARDOWN = re.compile(
    r"afterEach\s*\(|afterAll\s*\(|\.off\s*\(|removeListener|removeAllListeners"
    r"|\.close\s*\(\s*\)|clearCookies\s*\("
)

# Idempotency: unique-per-run data or a length-delta assertion makes a create-then-
# check test re-runnable; a hardcoded full URL in the test body is an anti-pattern.
_UNIQUE_DATA = re.compile(
    r"Date\.now\s*\(|randomUUID|crypto\.getRandomValues|Math\.random|\bnanoid\b|\bfaker\."
)
_LENGTH_DELTA = re.compile(r"\.length\b|toHaveCount\s*\(")
# A hardcoded URL is a full literal passed straight to a navigation/request call —
# NOT a URL in ``test.use({ baseURL })`` config, which is the recommended pattern.
_HARDCODED_URL = re.compile(
    r"(?:goto|fetch|route|routeWebSocket|waitForResponse|waitForRequest|waitForURL"
    r"|connectOverCDP|request\.\w+)\s*\(\s*[`'\"]\s*https?://",
    re.IGNORECASE,
)

# Code smells (per Playwright best-practices): reaching into the DOM or manual
# visibility checks instead of locators/web-first assertions. ``page.evaluate`` to
# read performance/timing is legitimate (the perf scenario needs it), so only
# DOM-reaching evaluate (querySelector / document.*) counts as a smell.
_SMELL_PATTERNS = (
    re.compile(r"querySelector(All)?\s*\(|document\.(getElement|querySelector)"),
    re.compile(r"\.evaluate\s*\([^)]*\b(document|querySelector|innerHTML|childNodes|children)\b"),
    re.compile(r"\.\$\$?\s*\(|page\.\$\$?eval\b"),  # legacy ElementHandle DOM APIs
    re.compile(r"\.isVisible\s*\(\s*\)|\.isHidden\s*\(\s*\)|\.textContent\s*\(\s*\)\s*[=!]=="),
)


def _locator_quality(scan_code: str) -> float:
    """Grade locator strategy: getByRole > getByLabel/Text > getByTestId > css > xpath."""
    weighted = 0.0
    total = 0
    for pattern, weight in _LOCATOR_TIERS:
        n = len(re.findall(pattern, scan_code))
        weighted += n * weight
        total += n
    brittle = len(_BRITTLE_SELECTOR.findall(scan_code))
    css = max(0, len(_CSS_LOCATOR.findall(scan_code)) - brittle)
    weighted += css * 0.4 + brittle * 0.1
    total += css + brittle
    return (weighted / total) if total else float("nan")


def _assertion_quality(scan_full: str) -> float:
    """Fraction of assertions that are web-first/auto-retrying vs manual extraction."""
    good = len(_WEBFIRST_ASSERT.findall(scan_full))
    manual = len(_MANUAL_ASSERT.findall(scan_full))
    return (good / (good + manual)) if (good + manual) else float("nan")


def _waiting_quality(scan_full: str) -> tuple[float, bool]:
    good = bool(_GOOD_WAIT.search(scan_full))
    arbitrary = bool(_ARBITRARY_WAIT.search(scan_full))
    if not good and not arbitrary:
        return float("nan"), arbitrary  # no waiting decisions to judge
    if good and not arbitrary:
        return 1.0, arbitrary
    if good and arbitrary:
        return 0.5, arbitrary
    return 0.0, arbitrary


def _teardown_hygiene(scan_full: str) -> float:
    if not _NEEDS_TEARDOWN.search(scan_full):
        return float("nan")  # simple test; Playwright isolates each context
    return 1.0 if _HAS_TEARDOWN.search(scan_full) else 0.0


# DRY: repeated setup/action statements (e.g. an inline login copy-pasted into every
# test) signal duplication a helper/fixture/loop would remove. Strings are kept so
# assertions on different elements are not falsely seen as duplicates.
_STATEMENT = re.compile(r"^\s*(await\s+.+|expect\s*\(.+)$", re.M)


def _dry_score(scan_code: str) -> float:
    """1.0 = no duplicated statements; lower = more copy-paste. ``nan`` if too small."""
    stmts = [re.sub(r"\s+", " ", m.group(1)).strip() for m in _STATEMENT.finditer(scan_code)]
    if len(stmts) < 4:
        return float("nan")  # too few statements to judge repetition fairly
    seen: set[str] = set()
    dup = 0
    for s in stmts:
        if s in seen:
            dup += 1
        else:
            seen.add(s)
    return 1.0 - dup / len(stmts)


def score_craft(sample: Sample, parsed: str, ctx: ScoreContext) -> ScoreRow:
    """Objective craft signals for an e2e test (locators, assertions, waiting, idempotency).

    All values are reported, never folded into the headline composite until
    validated against the human golden set.
    """
    del sample, ctx
    code = parsed if isinstance(parsed, str) else str(parsed)
    scan_full = _strip_js_noise(code)  # comments + strings removed (token signals)
    scan_code = _strip_comments(code)  # strings kept (locators live in strings)
    waiting, arbitrary = _waiting_quality(scan_full)
    fragile = bool(_BRITTLE_SELECTOR.search(scan_code))
    smell = fragile or any(rx.search(scan_full) for rx in _SMELL_PATTERNS)
    return {
        "locator_quality": _locator_quality(scan_code),
        "assertion_quality": _assertion_quality(scan_full),
        "waiting_quality": waiting,
        "uses_arbitrary_timeout": arbitrary,
        "teardown_hygiene": _teardown_hygiene(scan_full),
        "uses_unique_data": bool(_UNIQUE_DATA.search(scan_full))
        or bool(_LENGTH_DELTA.search(scan_full)),
        "uses_hardcoded_url": bool(_HARDCODED_URL.search(scan_code)),
        "uses_fragile_selector": fragile,
        "has_code_smell": smell,
        # Report-only until validated against the golden set; not yet in the composite.
        "dry_score": _dry_score(scan_code),
    }


def _parses(code: str, language: str) -> bool:
    if language == "python":
        try:
            ast.parse(code)
        except SyntaxError:
            return False
        return True
    # For JS/TS we only do a light brace-balance heuristic (no JS parser dependency).
    # Strip comments and strings first so braces inside them do not unbalance the count.
    stripped = _strip_js_noise(code)
    return stripped.count("{") == stripped.count("}") and bool(code.strip())
