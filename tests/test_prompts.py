from __future__ import annotations

from qabench.prompts import available_tracks, load_prompt, prompt_hash


def test_available_tracks() -> None:
    tracks = available_tracks()
    assert set(tracks) == {
        "unit_test_gen",
        "bug_localization",
        "test_case_design",
        "e2e_ui",
        "e2e_advanced",
        "e2e_repair",
    }


def test_load_prompt_nonempty() -> None:
    assert load_prompt("unit_test_gen").strip()


def test_prompt_hash_is_stable_and_short() -> None:
    h1 = prompt_hash("hello")
    h2 = prompt_hash("hello")
    assert h1 == h2
    assert len(h1) == 12
    assert prompt_hash("hello") != prompt_hash("world")
