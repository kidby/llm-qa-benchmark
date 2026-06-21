from __future__ import annotations

from qabench.parsing import extract_code_block, extract_json


def test_extract_python_block() -> None:
    text = "intro\n```python\nx = 1\n```\ntrailer"
    assert extract_code_block(text, prefer=("python",)) == "x = 1"


def test_extract_prefers_language() -> None:
    text = "```js\na\n```\n```python\nb\n```"
    assert extract_code_block(text, prefer=("python",)) == "b"


def test_extract_no_fence_returns_stripped() -> None:
    assert extract_code_block("  hello  ") == "hello"


def test_extract_json_from_fence() -> None:
    assert extract_json('```json\n{"a": 1}\n```') == {"a": 1}


def test_extract_json_inline() -> None:
    assert extract_json('noise {"line": 9} more') == {"line": 9}


def test_extract_json_invalid_returns_empty() -> None:
    assert extract_json("no json here") == {}
