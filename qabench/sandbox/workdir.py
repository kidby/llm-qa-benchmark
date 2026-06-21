"""Filesystem helpers shared by the local and Docker sandboxes."""

from __future__ import annotations

from pathlib import Path


def write_files(workdir: Path, files: dict[str, str]) -> None:
    """Write ``{relative_path: content}`` into ``workdir``, creating parent dirs."""
    for rel, content in files.items():
        path = workdir / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


def decode(raw: str | bytes | None) -> str:
    """Decode subprocess output (bytes or str) to text, tolerating bad bytes."""
    if raw is None:
        return ""
    return raw.decode("utf-8", "replace") if isinstance(raw, bytes) else raw
