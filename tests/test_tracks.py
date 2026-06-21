from __future__ import annotations

from qabench.tracks import TRACKS, get_track, select_tracks


def test_tracks_registered() -> None:
    assert set(TRACKS) == {
        "unit_test_gen",
        "bug_localization",
        "test_case_design",
        "e2e_ui",
        "e2e_advanced",
        "e2e_repair",
    }


def test_track_categories() -> None:
    from qabench.tracks import CATEGORY_BY_TRACK

    assert CATEGORY_BY_TRACK["unit_test_gen"] == "component"
    assert CATEGORY_BY_TRACK["bug_localization"] == "component"
    assert CATEGORY_BY_TRACK["test_case_design"] == "component"
    assert CATEGORY_BY_TRACK["e2e_ui"] == "system"
    assert CATEGORY_BY_TRACK["e2e_advanced"] == "system"


def test_e2e_advanced_dataset_and_implicit_prompt() -> None:
    track = TRACKS["e2e_advanced"]
    samples = track.load_dataset()
    assert len(samples) == 10  # 9 technique scenarios + the multi-test login suite
    assert {s.payload["expected_pattern"] for s in samples} == {
        "structure",
        "fixtures",
        "network",
        "polling",
        "api",
        "download",
        "accessibility",
        "performance",
        "realtime",
    }
    # The technique must never be named in any prompt the model sees.
    for s in samples:
        blob = " ".join(m.content.lower() for m in track.build_prompt(s))
        for leak in ("page object", "fixture", "intercept", "route(", "expected_pattern"):
            assert leak not in blob, f"{s.id} prompt leaks '{leak}'"


def test_e2e_repair_dataset_and_prompt() -> None:
    track = TRACKS["e2e_repair"]
    samples = track.load_dataset()
    assert len(samples) == 4
    sample = samples[0]
    assert sample.payload["broken_test"] and sample.payload["error"]
    # One sample carries an existing page-object structure the fix must preserve.
    keep = next(s for s in samples if s.id == "keep_page_objects")
    assert keep.payload["expected_pattern"] == "structure"
    # The prompt must include both the failing test and the runner output.
    blob = " ".join(m.content for m in track.build_prompt(sample))
    assert sample.payload["error"][:40] in blob
    assert "Failing test" in blob


def test_each_track_loads_its_dataset() -> None:
    for name, track in TRACKS.items():
        samples = track.load_dataset()
        assert samples, f"track {name} has no samples"
        for s in samples:
            assert s.track == name
            msgs = track.build_prompt(s)
            assert msgs[0].role == "system"
            assert msgs[-1].role == "user"


def test_unit_test_gen_has_mutants() -> None:
    samples = TRACKS["unit_test_gen"].load_dataset()
    assert all(s.payload["mutants"] for s in samples)


def test_select_tracks() -> None:
    assert [t.name for t in select_tracks("unit_test_gen")] == ["unit_test_gen"]
    assert len(select_tracks("all")) == 6


def test_get_track_unknown_raises() -> None:
    import pytest

    with pytest.raises(KeyError):
        get_track("nope")


def test_unit_parse_extracts_code() -> None:
    parsed = TRACKS["unit_test_gen"].parse_output("```python\nassert True\n```")
    assert parsed == "assert True"


def test_bug_parse_extracts_json() -> None:
    parsed = TRACKS["bug_localization"].parse_output('{"line": 3}')
    assert parsed == {"line": 3}
