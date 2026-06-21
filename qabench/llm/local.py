"""Local provider — an OpenAI-compatible server such as Ollama or vLLM."""

from __future__ import annotations

from qabench.config import Settings
from qabench.llm.openai_compat import openai_compatible_generate
from qabench.types import Generate


def make_local(settings: Settings) -> Generate:
    """Build a ``generate`` function for a local OpenAI-compatible endpoint."""
    base = settings.local_base_url.rstrip("/")
    return openai_compatible_generate(
        url=f"{base}/chat/completions",
        api_key=settings.local_api_key,
        timeout_s=settings.request_timeout_s,
        temperature=settings.temperature,
    )
