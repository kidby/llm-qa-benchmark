"""The Track value type and shared dataset/prompt helpers.

A Track is *data*: a frozen dataclass wiring together small functions. There is no
inheritance — adding a track means constructing one of these and registering it.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from qabench.config import DATASETS_DIR
from qabench.prompts import load_prompt
from qabench.types import Feedback, Msg, Parsed, Sample, Scorer

LoadDataset = Callable[[], list[Sample]]
BuildPrompt = Callable[[Sample], list[Msg]]
ParseOutput = Callable[[str], Parsed]


@dataclass(frozen=True)
class Track:
    """One benchmark task: dataset + prompt builder + parser + scorers."""

    name: str
    language: str
    image: str
    load_dataset: LoadDataset
    build_prompt: BuildPrompt
    parse_output: ParseOutput
    scorers: tuple[Scorer, ...]
    feedback: Feedback | None = None
    supports_multishot: bool = field(default=False)
    # "component" (unit/spec-level) or "system" (browser/integration-level).
    category: str = "component"
    # Whether this track counts toward the headline composite. Execution-grounded
    # tracks do; judge-only tracks (test_case_design) are reported separately.
    headline: bool = True


def sample_dirs(track: str) -> list[Path]:
    """Return the per-sample directories for a track's dataset, sorted by id."""
    root = DATASETS_DIR / track
    if not root.is_dir():
        return []
    return sorted(p for p in root.iterdir() if p.is_dir())


def system_user_messages(track: str, user_content: str) -> list[Msg]:
    """Build a standard [system, user] message pair for a track."""
    return [
        Msg(role="system", content=load_prompt(track)),
        Msg(role="user", content=user_content),
    ]
