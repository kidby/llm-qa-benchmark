"""Runtime configuration: paths, API keys, and tunables loaded from env/.env."""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MODELS_PATH = REPO_ROOT / "config" / "models.toml"
DATASETS_DIR = REPO_ROOT / "datasets"
PROMPTS_DIR = REPO_ROOT / "prompts"
RESULTS_DIR = REPO_ROOT / "results"


class Settings(BaseSettings):
    """Process-wide settings, populated from environment variables and ``.env``."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    openrouter_api_key: str = ""
    local_base_url: str = "http://localhost:11434/v1"
    local_api_key: str = "ollama"

    # OpenRouter model id used by the LLM judges; overridable with JUDGE_MODEL.
    # Opus is the strongest available judge — judging quality matters more than
    # cost here, and the judges run at temperature 0 for determinism.
    judge_model: str = "anthropic/claude-opus-4.8"

    # Anthropic-direct credentials for the batch re-judge path (`qabench rejudge`).
    # Judges are an ideal batch workload (offline, deterministic, high volume), and
    # the Message Batches API runs them at 50% of standard price. Generation stays
    # on OpenRouter; only the judges use this. The model id is the Anthropic-direct
    # form (no `anthropic/` provider prefix).
    anthropic_api_key: str = ""
    anthropic_judge_model: str = "claude-opus-4-8"

    # Generation sampling temperature. Above 0 so repeated trials vary, which is
    # the basis for averaging over trials; the judges always run at temperature 0.
    temperature: float = 1.0

    concurrency: int = 8
    request_timeout_s: int = 120
    max_retries: int = 4

    sandbox: str = "auto"  # auto | docker | local
    sandbox_timeout_s: int = 120


def load_settings() -> Settings:
    """Load settings from environment and ``.env``."""
    return Settings()
