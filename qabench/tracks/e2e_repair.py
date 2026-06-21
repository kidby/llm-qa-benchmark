"""Track: repair a failing Playwright test from its runner output.

Each sample is a broken Playwright test plus the failure output the Playwright
runner produced (error, call log, code frame) — the artifact an engineer would
paste into an assistant. The model must return a corrected test that passes
against the running app. Scoring reuses ``score_e2e``: the fix is run for real.
"""

from __future__ import annotations

import json

from qabench.parsing import extract_code_block
from qabench.sandbox import PLAYWRIGHT_IMAGE
from qabench.scoring.e2e import score_e2e
from qabench.scoring.judges import score_review
from qabench.scoring.static_checks import score_craft, score_e2e_patterns
from qabench.tracks.base import Track, sample_dirs, system_user_messages
from qabench.types import Msg, Sample

NAME = "e2e_repair"


def load_dataset() -> list[Sample]:
    """Load each broken test, its Playwright failure output, and success condition."""
    samples: list[Sample] = []
    for d in sample_dirs(NAME):
        meta = json.loads((d / "meta.json").read_text(encoding="utf-8"))
        broken = (d / "broken.spec.ts").read_text(encoding="utf-8")
        error = (d / "error.txt").read_text(encoding="utf-8")
        samples.append(
            Sample(
                id=d.name,
                track=NAME,
                language="typescript",
                payload={
                    "broken_test": broken,
                    "error": error,
                    "base_url": meta.get("base_url", "http://localhost:8081"),
                    "success": meta.get("success_assertion", ""),
                    # Scoring-only; when set, checks the fix preserves the structure.
                    "expected_pattern": meta.get("expected_pattern", ""),
                },
            )
        )
    return samples


def build_prompt(sample: Sample) -> list[Msg]:
    """Present the failing test, the runner output, and the success condition."""
    p = sample.payload
    user = (
        f"Base URL: {p['base_url']}\n\n"
        f"Failing test:\n```ts\n{p['broken_test']}\n```\n\n"
        f"Playwright runner output:\n```\n{p['error']}\n```\n\n"
        f"Success condition: {p['success']}"
    )
    return system_user_messages(NAME, user)


def parse_output(text: str) -> str:
    """Extract the corrected Playwright TypeScript test."""
    return extract_code_block(text, prefer=("ts", "typescript", "js", "javascript"))


TRACK = Track(
    name=NAME,
    language="typescript",
    image=PLAYWRIGHT_IMAGE,
    load_dataset=load_dataset,
    build_prompt=build_prompt,
    parse_output=parse_output,
    scorers=(score_e2e, score_e2e_patterns, score_craft, score_review),
    category="system",
)
