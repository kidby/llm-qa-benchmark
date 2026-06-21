"""LLM provider layer: one ``generate`` function per provider, dispatched by name."""

from __future__ import annotations

from qabench.llm.client import build_completer
from qabench.llm.fake import make_fake

__all__ = ["build_completer", "make_fake"]
