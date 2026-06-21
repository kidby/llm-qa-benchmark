"""Track: bug detection & localization. Objective (line accuracy + repair run)."""

from __future__ import annotations

import json

from qabench.parsing import extract_json
from qabench.sandbox import PYTHON_IMAGE
from qabench.scoring.judges import score_localization_explanation
from qabench.scoring.localization import score_localization
from qabench.tracks.base import Track, sample_dirs, system_user_messages
from qabench.types import Msg, Sample

NAME = "bug_localization"


def load_dataset() -> list[Sample]:
    """Load buggy modules, fault lines, and (optional) hidden tests."""
    samples: list[Sample] = []
    for d in sample_dirs(NAME):
        meta = json.loads((d / "meta.json").read_text(encoding="utf-8"))
        source = (d / "buggy.py").read_text(encoding="utf-8")
        test_path = d / "test_hidden.py"
        test = test_path.read_text(encoding="utf-8") if test_path.exists() else None
        samples.append(
            Sample(
                id=d.name,
                track=NAME,
                language="python",
                payload={
                    "source": source,
                    "module_name": meta["module_name"],
                    "fault_lines": meta["fault_lines"],
                    "symptom": meta.get("symptom", ""),
                    "test": test,
                },
            )
        )
    return samples


def build_prompt(sample: Sample) -> list[Msg]:
    """Present the numbered buggy source and the symptom."""
    source = sample.payload["source"]
    numbered = "\n".join(f"{i + 1:>3}  {line}" for i, line in enumerate(source.splitlines()))
    symptom = sample.payload.get("symptom", "")
    user = f"Symptom: {symptom}\n\nCode under test (line numbers shown):\n```\n{numbered}\n```"
    return system_user_messages(NAME, user)


def parse_output(text: str) -> dict[str, object]:
    """Extract the localization JSON object."""
    return extract_json(text)


TRACK = Track(
    name=NAME,
    language="python",
    image=PYTHON_IMAGE,
    load_dataset=load_dataset,
    build_prompt=build_prompt,
    parse_output=parse_output,
    scorers=(score_localization, score_localization_explanation),
)
