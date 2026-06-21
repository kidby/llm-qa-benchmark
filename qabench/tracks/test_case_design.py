"""Track: test-case design from a natural-language spec. Judge-led scoring."""

from __future__ import annotations

import json

from qabench.parsing import extract_json
from qabench.sandbox import PYTHON_IMAGE
from qabench.scoring.judges import score_test_case_design
from qabench.tracks.base import Track, sample_dirs, system_user_messages
from qabench.types import Msg, Sample

NAME = "test_case_design"


def load_dataset() -> list[Sample]:
    """Load natural-language requirements and their reference edge-case sets."""
    samples: list[Sample] = []
    for d in sample_dirs(NAME):
        requirement = (d / "requirement.md").read_text(encoding="utf-8")
        ref_path = d / "reference_classes.json"
        reference = json.loads(ref_path.read_text(encoding="utf-8")) if ref_path.exists() else {}
        samples.append(
            Sample(
                id=d.name,
                track=NAME,
                language="none",
                payload={"requirement": requirement, "reference": reference},
            )
        )
    return samples


def build_prompt(sample: Sample) -> list[Msg]:
    """Present the requirement to design test cases for."""
    return system_user_messages(NAME, str(sample.payload["requirement"]))


def parse_output(text: str) -> dict[str, object]:
    """Extract the test-case-suite JSON."""
    return extract_json(text)


TRACK = Track(
    name=NAME,
    language="none",
    image=PYTHON_IMAGE,
    load_dataset=load_dataset,
    build_prompt=build_prompt,
    parse_output=parse_output,
    scorers=(score_test_case_design,),
    # Judge-only (no execution): reported separately, excluded from the headline.
    headline=False,
)
