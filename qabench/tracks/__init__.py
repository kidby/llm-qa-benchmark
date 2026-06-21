"""Track registry — the one dict the runner and scorer iterate over.

Adding a track is: write a module exposing a ``TRACK`` value, import it here, and
add it to ``TRACKS``. Nothing else in the harness changes.
"""

from __future__ import annotations

from qabench.tracks.base import Track
from qabench.tracks.bug_localization import TRACK as BUG_LOCALIZATION
from qabench.tracks.e2e_advanced import TRACK as E2E_ADVANCED
from qabench.tracks.e2e_repair import TRACK as E2E_REPAIR
from qabench.tracks.e2e_ui import TRACK as E2E_UI
from qabench.tracks.test_case_design import TRACK as TEST_CASE_DESIGN
from qabench.tracks.unit_test_gen import TRACK as UNIT_TEST_GEN

TRACKS: dict[str, Track] = {
    t.name: t
    for t in (UNIT_TEST_GEN, BUG_LOCALIZATION, TEST_CASE_DESIGN, E2E_UI, E2E_ADVANCED, E2E_REPAIR)
}

# Two-tier grouping for reporting: component-level vs system-level tests.
CATEGORY_BY_TRACK: dict[str, str] = {name: t.category for name, t in TRACKS.items()}

# Execution-grounded tracks that count toward the headline composite. Judge-only
# tracks (test_case_design) are reported per-track but excluded from the rollup.
HEADLINE_TRACKS: frozenset[str] = frozenset(name for name, t in TRACKS.items() if t.headline)

__all__ = [
    "CATEGORY_BY_TRACK",
    "HEADLINE_TRACKS",
    "TRACKS",
    "Track",
    "get_track",
    "select_tracks",
]


def get_track(name: str) -> Track:
    """Look up a track by name, raising ``KeyError`` if unknown."""
    return TRACKS[name]


def select_tracks(selector: str) -> list[Track]:
    """Resolve a ``--track`` selector: ``all`` or a comma-separated list of names."""
    if selector == "all":
        return list(TRACKS.values())
    names = [s.strip() for s in selector.split(",") if s.strip()]
    missing = [n for n in names if n not in TRACKS]
    if missing:
        raise KeyError(f"Unknown track(s): {', '.join(missing)}")
    return [TRACKS[n] for n in names]
