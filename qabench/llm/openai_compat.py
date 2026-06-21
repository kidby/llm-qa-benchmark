"""A generate function for any OpenAI-compatible chat-completions endpoint.

Shared by the OpenRouter and local providers (and usable for any other
OpenAI-compatible gateway, e.g. Vercel AI Gateway, Groq, Together, Azure).
"""

from __future__ import annotations

import time

import httpx

from qabench.llm.base import compute_cost, to_openai_messages
from qabench.types import Generate, Model, Msg, Response


def openai_compatible_generate(
    *, url: str, api_key: str, timeout_s: int, temperature: float = 1.0
) -> Generate:
    """Build a generate function for an OpenAI-compatible chat endpoint."""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    def generate(model: Model, messages: list[Msg]) -> Response:
        payload: dict[str, object] = {
            "model": model.id,
            "messages": to_openai_messages(messages),
            "temperature": temperature,
        }
        start = time.perf_counter()
        resp = httpx.post(url, headers=headers, json=payload, timeout=timeout_s)
        resp.raise_for_status()
        latency = time.perf_counter() - start
        data = resp.json()
        text = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {})
        tokens_in = int(usage.get("prompt_tokens", 0))
        tokens_out = int(usage.get("completion_tokens", 0))
        return Response(
            text=text,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            latency_s=latency,
            cost=compute_cost(model, tokens_in, tokens_out),
        )

    return generate
