"""Helpers shared by the provider generate functions."""

from __future__ import annotations

from qabench.types import Model, Msg


def compute_cost(model: Model, tokens_in: int, tokens_out: int) -> float:
    """Dollar cost of a call given token usage and the model's per-Mtok rates."""
    return (
        tokens_in / 1_000_000 * model.input_cost_per_mtok
        + tokens_out / 1_000_000 * model.output_cost_per_mtok
    )


def to_openai_messages(messages: list[Msg]) -> list[dict[str, str]]:
    """Convert messages to the OpenAI/OpenRouter ``messages`` array shape."""
    return [{"role": m.role, "content": m.content} for m in messages]
