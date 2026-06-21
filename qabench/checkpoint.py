"""Result persistence and resume support.

Row-level results (responses, scored) are stored as JSONL, one object per line:
append-friendly for resumable runs, type-preserving, and robust to the multi-line
code they contain. The aggregated summary is a flat CSV. Rows are keyed on
``(model_slug, track, sample_id, trial)``; re-running a run id skips keys already
present in ``responses.jsonl``, and deleting a line lets that row be retried.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from qabench.config import RESULTS_DIR

KEY_COLUMNS = ("model_slug", "track", "sample_id", "trial")


def run_dir(run_id: str) -> Path:
    """Return (and create) the directory for a run id."""
    d = RESULTS_DIR / run_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def responses_path(run_id: str) -> Path:
    """Path to the raw responses JSONL for a run."""
    return run_dir(run_id) / "responses.jsonl"


def scored_path(run_id: str) -> Path:
    """Path to the scored JSONL for a run."""
    return run_dir(run_id) / "scored.jsonl"


def summary_path(run_id: str) -> Path:
    """Path to the aggregated summary CSV for a run."""
    return run_dir(run_id) / "summary.csv"


def report_path(run_id: str) -> Path:
    """Path to the rendered Markdown report for a run."""
    return run_dir(run_id) / "report.md"


def _json_default(value: object) -> object:
    """Coerce numpy scalars and pandas NA to JSON-native values."""
    item = getattr(value, "item", None)
    if callable(item):  # numpy scalar -> python scalar
        return item()
    return None  # pandas NaT / NA fall through to null


def append_row(path: Path, row: dict[str, Any]) -> None:
    """Append one row to a JSONL file, preserving native types."""
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, default=_json_default) + "\n")


def load_done_keys(path: Path) -> set[tuple[str, ...]]:
    """Return the set of completed ``(model_slug, track, sample_id, trial)`` keys."""
    if not path.exists():
        return set()
    keys: set[tuple[str, ...]] = set()
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            keys.add(tuple(str(row.get(col)) for col in KEY_COLUMNS))
    return keys


def read_jsonl(path: Path) -> pd.DataFrame:
    """Read a JSONL results file into a DataFrame (empty frame if missing)."""
    if not path.exists():
        return pd.DataFrame()
    return pd.read_json(path, lines=True)


def read_csv(path: Path) -> pd.DataFrame:
    """Read a results CSV into a DataFrame (empty frame if missing)."""
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)
