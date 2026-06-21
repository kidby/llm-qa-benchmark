Guidance for working in this repository.

### What this is

An execution-based LLM benchmark for QA & test automation. It generates model outputs, **runs**
them in a sandbox, and scores objectively (mutation kill, coverage, repair execution, e2e pass)
plus LLM judges. See `README.md` and `docs/architecture.md`.

### Design rules

- **Composition over inheritance.** No ABC hierarchies, no Template Method. A track is a `Track`
  dataclass of functions; scorers/providers/metrics are plain functions in registries (dicts).
- **Extensions are data.** Adding a model = one JSON entry; a metric = one function in `METRICS`;
  a track = one module + a dict entry. Keep it that way.
- **Everything stays `mypy --strict` clean and tested offline.** Use the fake LLM
  (`qabench.llm.make_fake`) and `LocalSandbox` so tests need no network or Docker.

### Commands

```bash
uv sync --extra dev --extra dashboard
uv run ruff check . && uv run ruff format --check .
uv run mypy
uv run pytest -m "not docker and not live"        # offline; -m docker / -m live opt in
uv run qabench run --track unit_test_gen --models claude-haiku-4-5 --limit 1 --dry-run
```

### Layout

- `qabench/` — the harness package (typed, `py.typed`).
  - `llm/` providers + judges, `sandbox/` Docker+local, `tracks/` the four tracks,
    `scoring/` scorers + `metrics.py` registry, `runner.py`, `score.py`, `aggregate.py`,
    `report.py`, `checkpoint.py`, `main.py` (CLI).
- `dashboard/` — separate Reflex app (not in the package; excluded from mypy/coverage).
- `datasets/`, `prompts/`, `docker/` — fixtures/assets (excluded from ruff).
- `tests/` — unit + mocked-integration; `results/` — generated runs (gitignored).

### Notes

- The CLI's `run`/`score`/`dashboard` imports are lazy (inside the command) to keep startup fast.
- `results/<run_id>/` is keyed on `(model_slug, track, sample_id)`; re-running resumes.
- Don't add heavy deps to the core; dashboard-only deps go in the `[dashboard]` extra.
