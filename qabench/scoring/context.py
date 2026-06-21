"""The concrete scoring context handed to every scorer."""

from __future__ import annotations

from dataclasses import dataclass

from qabench.config import Settings
from qabench.llm.client import build_completer
from qabench.sandbox import get_sandbox
from qabench.types import Generate, Sandbox


@dataclass(frozen=True)
class Context:
    """Bundles the sandbox and LLM judge passed to scorers."""

    sandbox: Sandbox
    judge: Generate
    judge_model_id: str


def build_context(settings: Settings, *, judge_override: Generate | None = None) -> Context:
    """Construct a scoring context from settings.

    Args:
        settings: Runtime settings.
        judge_override: A fake/alternate judge ``generate`` (used by tests).
    """
    # Judges run deterministically (temperature 0) regardless of generation temp.
    judge = judge_override or build_completer(settings.model_copy(update={"temperature": 0.0}))
    return Context(
        sandbox=get_sandbox(settings),
        judge=judge,
        judge_model_id=settings.judge_model,
    )
