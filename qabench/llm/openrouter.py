"""OpenRouter provider — access to many frontier models via one OpenAI-style API."""

from __future__ import annotations

from qabench.config import Settings
from qabench.llm.openai_compat import openai_compatible_generate
from qabench.types import Generate

_URL = "https://openrouter.ai/api/v1/chat/completions"


def make_openrouter(settings: Settings) -> Generate:
    """Build an OpenRouter ``generate`` function bound to the given settings."""
    return openai_compatible_generate(
        url=_URL,
        api_key=settings.openrouter_api_key,
        timeout_s=settings.request_timeout_s,
        temperature=settings.temperature,
    )
