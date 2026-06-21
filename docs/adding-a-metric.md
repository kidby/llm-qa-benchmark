# Adding a Metric

Unlike adding a model, which is a config-only TOML entry, a metric is a small code change, since a
metric is an arbitrary reduction over a pandas DataFrame. It remains a single edit: add one function
to the `METRICS` dictionary in [`qabench/scoring/metrics.py`](../qabench/scoring/metrics.py). No
other changes are required.

```python
def avg_latency(df: pd.DataFrame) -> float:
    """Mean per-sample latency in seconds."""
    return _mean(df, "latency_s")

METRICS = {
    # ...existing entries...
    "avg_latency": avg_latency,
}
```

The metric is then surfaced automatically as a column in `summary.csv`, a row in `report.md` once
added to the report's column list, and a series in the dashboard's metric explorer, since
`available_metrics()` reads `METRICS`.

## Conventions

- Return `float("nan")` when the inputs are absent for a track. The helpers `_mean`, `_bool_mean`,
  and `_rate` already do this, so prefer them.
- If a metric requires a raw field that is not yet emitted, have the relevant scorer return it.
  Scorers and metrics are decoupled by column name.

## Verification

```bash
uv run qabench score <run_id>
uv run python -c "import pandas as pd; print('avg_latency' in pd.read_csv('results/<run_id>/summary.csv').columns)"
```
