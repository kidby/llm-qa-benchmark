"""Model registry: load benchmarked models from ``config/models.toml``.

Adding a model is a single small JSON entry — no code changes. The ``provider``
field is the only thing that affects behaviour (it selects the generate function).
"""

from __future__ import annotations

import tomllib
from pathlib import Path

from pydantic import TypeAdapter

from qabench.config import DEFAULT_MODELS_PATH
from qabench.types import Model

_LIST_ADAPTER = TypeAdapter(list[Model])


def load_models(path: Path | None = None) -> list[Model]:
    """Load and validate the model registry from a TOML file of ``[[model]]`` tables.

    Args:
        path: Path to the registry file. Defaults to ``config/models.toml``.

    Returns:
        The list of models in file order.
    """
    p = path or DEFAULT_MODELS_PATH
    entries = tomllib.loads(p.read_text(encoding="utf-8"))["model"]
    return _LIST_ADAPTER.validate_python(entries)


def select_models(models: list[Model], selector: str) -> list[Model]:
    """Resolve a ``--models`` selector against the registry.

    Args:
        models: The full registry.
        selector: ``"all"`` (every non-skipped model), ``"*"`` (literally every
            model including skipped ones), or a comma-separated list of slugs.

    Returns:
        The selected models, preserving registry order.

    Raises:
        KeyError: If a requested slug is not in the registry.
    """
    if selector == "*":
        return list(models)
    if selector == "all":
        return [m for m in models if not m.skip_by_default]

    wanted = [s.strip() for s in selector.split(",") if s.strip()]
    by_slug = {m.slug: m for m in models}
    missing = [s for s in wanted if s not in by_slug]
    if missing:
        raise KeyError(f"Unknown model slug(s): {', '.join(missing)}")
    return [by_slug[s] for s in wanted]
