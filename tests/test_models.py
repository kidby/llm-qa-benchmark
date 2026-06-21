from __future__ import annotations

from pathlib import Path

import pytest
from qabench.models import load_models, select_models
from qabench.types import Model


def test_load_registry_defaults() -> None:
    models = load_models()
    assert models, "registry should not be empty"
    slugs = {m.slug for m in models}
    assert "claude-opus-4-8" in slugs


def test_label_defaults_to_slug() -> None:
    m = Model(slug="x", id="vendor/x", provider="openrouter")
    assert m.label == "x"


def test_select_all_excludes_skipped() -> None:
    models = [
        Model(slug="a", id="a", provider="local"),
        Model(slug="b", id="b", provider="local", skip_by_default=True),
    ]
    assert [m.slug for m in select_models(models, "all")] == ["a"]
    assert [m.slug for m in select_models(models, "*")] == ["a", "b"]


def test_select_by_slug_preserves_request_order() -> None:
    models = [
        Model(slug="a", id="a", provider="local"),
        Model(slug="b", id="b", provider="local"),
    ]
    assert [m.slug for m in select_models(models, "b,a")] == ["b", "a"]


def test_select_unknown_slug_raises() -> None:
    with pytest.raises(KeyError):
        select_models([Model(slug="a", id="a", provider="local")], "nope")


def test_load_models_from_toml(tmp_path: Path) -> None:
    p = tmp_path / "models.toml"
    p.write_text('[[model]]\nslug = "s"\nid = "i"\nprovider = "openrouter"\n')
    models = load_models(p)
    assert models[0].provider == "openrouter"
    assert models[0].label == "s"  # defaults to slug
