"""System-prompt loading and hashing.

Each track has one Markdown system prompt under ``prompts/``. We record a short
SHA-256 hash of the prompt on every result row so runs are reproducible and
prompt changes are visible in the data.
"""

from __future__ import annotations

import hashlib
from functools import cache

from qabench.config import PROMPTS_DIR


def available_tracks() -> list[str]:
    """Return the track names that have a system prompt, sorted."""
    return sorted(p.stem for p in PROMPTS_DIR.glob("*.md"))


@cache
def load_prompt(track: str) -> str:
    """Return the system prompt text for ``track`` (cached)."""
    path = PROMPTS_DIR / f"{track}.md"
    return path.read_text(encoding="utf-8").strip()


def prompt_hash(text: str) -> str:
    """Return a short (12-char) SHA-256 hash of a prompt string."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]
