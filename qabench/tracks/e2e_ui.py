"""Track: E2E/UI automation. Execution (Playwright) + selector robustness."""

from __future__ import annotations

import json

from qabench.parsing import extract_code_block
from qabench.sandbox import PLAYWRIGHT_IMAGE
from qabench.scoring.e2e import score_e2e
from qabench.scoring.judges import score_review
from qabench.scoring.static_checks import score_craft, score_selector_robustness
from qabench.tracks.base import Track, sample_dirs, system_user_messages
from qabench.types import Msg, Sample

NAME = "e2e_ui"


def load_dataset() -> list[Sample]:
    """Load user-flow descriptions and their success assertions."""
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
                    "base_url": meta.get("base_url", "http://localhost:8080"),
                    "success": meta.get("success_assertion", ""),
                },
            )
        )
    return samples


def build_prompt(sample: Sample) -> list[Msg]:
    """Present the flow, base URL, and the success condition."""
    p = sample.payload
    user = (
        f"Base URL: {p['base_url']}\n\nUser flow:\n{p['flow']}\n\nSuccess condition: {p['success']}"
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
    scorers=(score_e2e, score_selector_robustness, score_craft, score_review),
    category="system",
)
