# Golden batch 01 — validation results

Human labels in `batch_01.md` (10 real model outputs) vs the automated detectors.
Run via the validation snippet against the exact worksheet code.

## Detector agreement: 10/10 exact, on a graded scale

`pattern_used` is graded — 1.0 full / 0.5 partial / 0.0 none (yes/partial/no) —
because the user distinguishes a proper tool from an acceptable-but-weaker form.
Final agreement is 10/10 exact against the human yes/partial/no labels.

Initial binary run agreed 6/10. The mismatches, all matching the human rubric,
revealed real gaps that were then fixed:

| Gap | Items | Fix |
|-----|-------|-----|
| `fixtures` only matched `test.extend(` | 3, 4 | credit `storageState` / setup-project `dependencies:` / `beforeAll` too |
| `polling` only matched `expect.poll`/`toPass` | 7, 8 | credit web-first auto-retrying assertions too — but only as **partial** |
| `uses_hardcoded_url` flagged any `https?://` | (FP on 2, 8) | only flag a literal URL passed to `goto`/`request`/`route`, not `test.use({ baseURL })` config |

**Graded strength (user's reversed judgment):** `expect.poll` / `toPass` /
`waitForResponse` are the proper polling tools (1.0); a web-first `toHaveText` with a
long timeout works but is the weaker fallback (0.5 — items 7, 8). For fixtures, a
custom fixture or setup project is full (1.0 — item 3), while building shared state
by hand in a `beforeAll` hook is partial (0.5 — item 4). `pattern_attempted` keeps
the binary "touched it at all" signal; `pattern_adoption` is now a mean of the
graded `pattern_used` (partial counts as a half).

Two earlier bugs were also caught while building this set: the comment-stripper ate
`http://` URLs (flipped 36 detections), and `extract_code_block` leaked a stray
fence on truncated output.

## Craft-signal alignment with human notes (no fitting)

- `uses_hardcoded_url` True on items 5, 7, 9 — the exact three the human flagged
  "incorrectly hardcodes URL"; False on the `baseURL`-config items 2, 8.
- `assertion_quality` 0.00 on items 1, 2 — the two dinged for manual
  `.status().toBe` / `.ok().toBeTruthy()` instead of `toBeOK`.
- `locator_quality` 0.70 on items 5, 6 ("testId in place of getByRole"); 0.96+ on
  the getByRole/Label items 9, 10.

## LLM review judge validation — FAILED the bar (stays unwired)

Ran `score_review` (Opus 4.8 judge, temp 0) on the same 10 outputs vs the human
craft (1-5) scores:

| # | human craft | judge review_score |
|---|-------------|--------------------|
| 1 | 3 | 0.82 |
| 2 | 4 | 0.72 |
| 3 | 4 | 0.94 |
| 4 | **2** | **0.80** |
| 5 | 4 | 0.85 |
| 6 | 4 | 0.93 |
| 7 | 3 | 0.90 |
| 8 | 5 | 0.90 |
| 9 | 3 | 0.73 |
| 10 | 4 | 0.92 |

**Spearman rank corr = 0.447** (weak). Two decisive failures:
- Item 4 — the human's worst (craft 2: messy, hand-rolled cookies, hooks-as-fixtures)
  — the judge scored **0.80**, near the top. It did not see the messiness, which is
  the exact nuance the judge was meant to add.
- Item 7 (human 3) scored 0.90; item 2 (human 4) scored 0.72 — the judge compresses
  everything into 0.72–0.94 and barely discriminates.

Using the strongest available judge (Opus) did not rescue it. **Conclusion: the LLM
review judge does NOT match human craft judgment on this evidence and must NOT feed
the headline.** The validated static craft detectors (above) carry the craft signal;
the review judge stays report-only/descriptive. Chasing the correlation by tuning the
rubric on N=10 would be overfitting — a larger labeled set is the only honest way to
revisit it.

## DRY metric — report-only, not yet validatable on this batch

`dry_score` (1.0 = no duplicated setup/action statements) is implemented but stays
report-only (NOT in the composite). On batch 01 it is mostly `nan`: the samples are
single-test files with nothing to repeat, and DRY only has meaning across multiple
tests. Notes:
- Item 9 (human loosely called it a "DRY violation") scored 1.00 — there is no
  literal statement duplication; the human's point was "3 helpers vs one class,"
  which is a structure choice, not repetition. So 1.00 is defensible.
- Item 3 scored 0.71 for `goto('/app')` + a locator repeated across its two tests —
  mild real duplication a fixture would remove.

DRY's real signal will appear on multi-test files (e.g. the `login_suite` scenario,
where a copy-pasted login across 5 tests scores low). It earns headline weight only
after validating there. Decision: keep, report-only, unweighted for now.

## Composite weighting decision (opinion is valid, but weighted low)

The user's call: keep the LLM review judge in scoring because code review is
opinionated and an LLM's opinion is a valid (minority) signal — but weight it low.
Final e2e composite terms: execution `multi_shot` (2.0) + `pattern_adoption` (2.0)
dominate; validated `craft_score` (1.0) and the general `design` judge (1.0); the
opinionated `review_score` enters at **0.5** (lowest). Eloquence was added as a
review-judge criterion (rides the 0.5 weight). SOLID was intentionally NOT added —
it does not map to Playwright specs. Judge model switched to Opus 4.8.

## Residual → motivated the LLM review judge (which then failed)

Item 4: human "partial", craft 2 (mixes hooks with fixtures, hand-rolled cookie
header). Static signals look clean. Nuance static rules cannot see — exactly the
case the structured review judge must cover. The review judge (`score_review`)
remains UNWIRED from the headline until validated the same way against human craft
scores.
