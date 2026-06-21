"""Track: advanced E2E patterns. Execution + implicit-technique detection.

Each sample's scenario implies a Playwright technique (page object model,
fixtures, network interception, polling, or API integration) without naming it.
``expected_pattern`` in the sample meta drives scoring but is never shown to the
model. Runs against the richer app in ``docker/advanced-app`` (port 8081).
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

NAME = "e2e_advanced"


def load_dataset() -> list[Sample]:
    """Load advanced E2E scenarios, their success assertions, and expected patterns."""
    samples: list[Sample] = []
    for d in sample_dirs(NAME):
        meta = json.loads((d / "meta.json").read_text(encoding="utf-8"))
        flow = (d / "flow.md").read_text(encoding="utf-8")
        samples.append(
            Sample(
                id=d.name,
                track=NAME,
                language="typescript",
                payload={
                    "flow": flow,
                    "base_url": meta.get("base_url", "http://localhost:8081"),
                    "success": meta.get("success_assertion", ""),
                    # Scoring-only; never placed into the prompt.
                    "expected_pattern": meta.get("expected_pattern", ""),
                },
            )
        )
    return samples


def build_prompt(sample: Sample) -> list[Msg]:
    """Present only the scenario, base URL, and success condition (no technique hints)."""
    p = sample.payload
    user = (
        f"Base URL: {p['base_url']}\n\nScenario:\n{p['flow']}\n\nSuccess condition: {p['success']}"
    )
    return system_user_messages(NAME, user)


def parse_output(text: str) -> str:
    """Extract the Playwright TypeScript test."""
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
