"""Helpers for extracting structured content from raw model text."""

from __future__ import annotations

import json
import re

_FENCE = re.compile(
    r"```(?P<lang>[a-zA-Z0-9_+-]*)\n(?P<body>.*?)```",
    re.DOTALL,
)
# An opening fence with no closing fence — e.g. a model whose output was truncated.
_OPEN_FENCE = re.compile(r"```[a-zA-Z0-9_+-]*\n(?P<body>.*)", re.DOTALL)
_JSON_OBJ = re.compile(r"\{.*\}", re.DOTALL)


def extract_code_block(text: str, *, prefer: tuple[str, ...] = ()) -> str:
    """Return the first fenced code block, preferring languages in ``prefer``.

    Handles a truncated output (an opening fence with no close) by returning the
    code after the opening fence, and falls back to the whole text when there is
    no fence at all — so a stray ``` marker never leaks into the parsed code.
    """
    blocks = [(m.group("lang").lower(), m.group("body")) for m in _FENCE.finditer(text)]
    if not blocks:
        open_match = _OPEN_FENCE.search(text)
        return open_match.group("body").strip() if open_match else text.strip()
    for wanted in prefer:
        for lang, body in blocks:
            if lang == wanted:
                return body.strip()
    return blocks[0][1].strip()


def extract_json(text: str) -> dict[str, object]:
    """Return the first JSON object in ``text`` (from a fence or inline), or ``{}``."""
    fenced = extract_code_block(text, prefer=("json",))
    for candidate in (fenced, text):
        match = _JSON_OBJ.search(candidate)
        if not match:
            continue
        try:
            parsed: object = json.loads(match.group(0))
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    return {}
