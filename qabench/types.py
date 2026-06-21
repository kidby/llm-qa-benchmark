"""Shared types: data models, aliases, and Protocols for the composition design.

The harness is built from plain functions wired together by data, not class
hierarchies. These Protocols and aliases keep that style fully type-checked.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal, Protocol

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    import pandas as pd

# --- Roles & messages -------------------------------------------------------

Role = Literal["system", "user", "assistant"]


class Msg(BaseModel):
    """A single chat message sent to a model."""

    role: Role
    content: str


# --- Model registry ---------------------------------------------------------

Provider = Literal["openrouter", "local"]


class Model(BaseModel):
    """A benchmarked model — one small entry in ``config/models.toml``.

    Adding a model is just adding one of these to the registry; only ``provider``
    affects behaviour (it selects the ``generate`` function).
    """

    slug: str = Field(..., description="Unique key used on the CLI and in result rows.")
    id: str = Field(..., description="Provider-specific model identifier.")
    provider: Provider = "openrouter"
    label: str = ""
    input_cost_per_mtok: float = 0.0
    output_cost_per_mtok: float = 0.0
    context_override: int | None = None
    skip_by_default: bool = False
    params_b: float | None = Field(
        default=None, description="Parameter count in billions, when disclosed (open models)."
    )

    def model_post_init(self, __context: Any) -> None:
        """Default the display label to the slug when not provided."""
        if not self.label:
            object.__setattr__(self, "label", self.slug)


# --- LLM responses ----------------------------------------------------------


class Response(BaseModel):
    """The result of a single model generation, with usage/cost accounting."""

    text: str
    tokens_in: int = 0
    tokens_out: int = 0
    latency_s: float = 0.0
    cost: float = 0.0


class Generate(Protocol):
    """A provider's generation function. One per provider, registered in a dict."""

    def __call__(self, model: Model, messages: list[Msg]) -> Response:
        """Generate a completion for ``messages`` using ``model``."""
        ...


# --- Datasets & samples -----------------------------------------------------


class Sample(BaseModel):
    """One benchmark item within a track.

    ``payload`` holds track-specific fields (source code, mutants, spec, flow,
    fault lines, ...). Keeping it a free-form dict lets each track define its own
    shape without subclassing.
    """

    id: str
    track: str
    language: Literal["python", "javascript", "typescript", "none"] = "python"
    prompt_context: str = ""
    payload: dict[str, Any] = Field(default_factory=dict)


# Parsed output of a model's raw text, track-specific (e.g. extracted code, JSON).
Parsed = Any

# A raw per-sample scorer result: column name -> value.
ScoreRow = dict[str, float | int | str | bool | None]


# --- Execution sandbox ------------------------------------------------------


class ExecResult(BaseModel):
    """The outcome of running a command in a sandbox."""

    exit_code: int
    stdout: str = ""
    stderr: str = ""
    timed_out: bool = False
    duration_s: float = 0.0

    @property
    def ok(self) -> bool:
        """True when the command exited cleanly and did not time out."""
        return self.exit_code == 0 and not self.timed_out


class Sandbox(Protocol):
    """Runs files+command in isolation. Docker and local implementations exist."""

    def run(
        self,
        *,
        image: str,
        files: dict[str, str],
        command: list[str],
        timeout_s: int = 120,
    ) -> ExecResult:
        """Write ``files`` into a workdir, run ``command``, return the result."""
        ...


# --- Scorers & metrics ------------------------------------------------------


class ScoreContext(Protocol):
    """Everything a scorer might need: a sandbox and an LLM judge."""

    @property
    def sandbox(self) -> Sandbox:
        """The execution sandbox."""
        ...

    @property
    def judge(self) -> Generate:
        """The LLM judge generate function."""
        ...

    @property
    def judge_model_id(self) -> str:
        """The model id used for judging."""
        ...


class Scorer(Protocol):
    """Scores one sample's parsed output, returning columns to merge into the row."""

    def __call__(self, sample: Sample, parsed: Parsed, ctx: ScoreContext) -> ScoreRow:
        """Return raw score fields for ``sample``."""
        ...


class Feedback(Protocol):
    """Multi-shot feedback: did the sample pass, and if not, what was wrong?"""

    def __call__(self, sample: Sample, parsed: Parsed, ctx: ScoreContext) -> tuple[bool, str]:
        """Return ``(passed, error_text)`` for the self-repair loop."""
        ...


class Metric(Protocol):
    """Rolls a per-sample DataFrame (one model+track group) into a single number."""

    def __call__(self, df: pd.DataFrame) -> float:
        """Compute the metric over the group."""
        ...
