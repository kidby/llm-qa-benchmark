"""Track: unit-test generation. Fully objective (validity, mutation, coverage)."""

from __future__ import annotations

import json

from qabench.parsing import extract_code_block
from qabench.sandbox import PYTHON_IMAGE
from qabench.scoring.execution import score_unit_tests, unit_test_feedback
from qabench.scoring.judges import score_design, score_hallucination
from qabench.scoring.static_checks import score_static_tests
from qabench.tracks.base import Track, sample_dirs, system_user_messages
from qabench.types import Msg, Sample

NAME = "unit_test_gen"


def load_dataset() -> list[Sample]:
    """Load source modules and their stored mutants from the dataset dir."""
    samples: list[Sample] = []
    for d in sample_dirs(NAME):
        meta = json.loads((d / "meta.json").read_text(encoding="utf-8"))
        source = (d / "source.py").read_text(encoding="utf-8")
        mutants = [p.read_text(encoding="utf-8") for p in sorted((d / "mutants").glob("*.py"))]
        samples.append(
            Sample(
                id=d.name,
                track=NAME,
                language="python",
                payload={
                    "source": source,
                    "module_name": meta["module_name"],
                    "mutants": mutants,
                },
            )
        )
    return samples


def build_prompt(sample: Sample) -> list[Msg]:
    """Ask for a test suite for the given module."""
    module = sample.payload["module_name"]
    source = sample.payload["source"]
    user = (
        f"Module name: `{module}` — import it as `from {module} import ...`.\n\n"
        f"```python\n{source}\n```"
    )
    return system_user_messages(NAME, user)


def parse_output(text: str) -> str:
    """Extract the Python test file from the model's reply."""
    return extract_code_block(text, prefer=("python", "py"))


TRACK = Track(
    name=NAME,
    language="python",
    image=PYTHON_IMAGE,
    load_dataset=load_dataset,
    build_prompt=build_prompt,
    parse_output=parse_output,
    scorers=(score_unit_tests, score_static_tests, score_hallucination, score_design),
    feedback=unit_test_feedback,
    supports_multishot=True,
)
