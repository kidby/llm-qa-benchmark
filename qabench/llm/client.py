"""Unified completion entrypoint: dispatch by provider, with retries.

``build_completer`` returns a single ``generate(model, messages) -> Response``
function. It picks the right provider function from a dict keyed on
``model.provider`` — so adding a provider is adding one entry here.
"""

from __future__ import annotations

import httpx
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from qabench.config import Settings
from qabench.llm.local import make_local
from qabench.llm.openrouter import make_openrouter
from qabench.types import Generate, Model, Msg, Provider, Response


def build_generators(
    settings: Settings, overrides: dict[Provider, Generate] | None = None
) -> dict[Provider, Generate]:
    """Build the provider -> generate-function map.

    Constructing a provider function does no network I/O (closures only), so both
    are built eagerly. ``overrides`` lets tests inject fakes.
    """
    generators: dict[Provider, Generate] = {
        "openrouter": make_openrouter(settings),
        "local": make_local(settings),
    }
    generators.update(overrides or {})
    return generators


def build_completer(
    settings: Settings, overrides: dict[Provider, Generate] | None = None
) -> Generate:
    """Return a retrying ``generate`` that dispatches on ``model.provider``."""
    generators = build_generators(settings, overrides)

    @retry(
        stop=stop_after_attempt(settings.max_retries),
        wait=wait_exponential(multiplier=1, min=1, max=20),
        retry=retry_if_exception(_is_transient),
        reraise=True,
    )
    def complete(model: Model, messages: list[Msg]) -> Response:
        return generators[model.provider](model, messages)

    return complete


def _is_transient(exc: BaseException) -> bool:
    """Retry on network errors and 5xx/429 responses; fail fast on the rest."""
    if isinstance(exc, httpx.TransportError | httpx.TimeoutException):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        code = exc.response.status_code
        return code == 429 or 500 <= code < 600
    return False
