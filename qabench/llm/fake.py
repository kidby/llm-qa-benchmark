"""A deterministic fake provider, used by tests so the suite needs no network."""

from __future__ import annotations

from collections.abc import Callable

from qabench.types import Generate, Model, Msg, Response

Responder = Callable[[Model, list[Msg]], str]


def make_fake(responder: Responder | dict[str, str] | str) -> Generate:
    """Build a fake ``generate`` function.

    Args:
        responder: Either a callable ``(model, messages) -> text``, a mapping of
            model slug -> canned text, or a single string returned for everything.

    Returns:
        A ``Generate`` that fabricates token counts and zero latency.
    """
    if isinstance(responder, str):
        text_for: Responder = lambda _m, _msgs: responder  # noqa: E731
    elif isinstance(responder, dict):
        mapping = responder
        text_for = lambda m, _msgs: mapping.get(m.slug, "")  # noqa: E731
    else:
        text_for = responder

    def generate(model: Model, messages: list[Msg]) -> Response:
        text = text_for(model, messages)
        tokens_in = sum(len(m.content.split()) for m in messages)
        tokens_out = len(text.split())
        return Response(text=text, tokens_in=tokens_in, tokens_out=tokens_out)

    return generate
