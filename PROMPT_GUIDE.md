# Prompt Guide

System prompts are stored in `prompts/<track>.md`, one per track. A short SHA-256 hash of each
prompt is recorded on every result row as `prompt_hash` and in `run_manifest.json`, making prompt
changes visible in the data and keeping runs reproducible.

```bash
uv run qabench show-prompt --track all   # print prompts and their hashes
```

## Principles

- **Require a single, parseable artifact.** Request test suites in one fenced code block and
  structured tasks as a single JSON object. The parsers in `qabench/parsing.py` extract the first
  fenced block or inline JSON, so requesting only the artifact minimizes formatting noise and failed
  parses.
- **Specify the contract, not the solution.** State the framework, import path, and output shape.
  Hinting at specific test cases undermines the measurement.
- **Make the objective explicit.** For `unit_test_gen`, the prompt requires that tests pass against
  the correct implementation and cover edge and error paths, because the scorer penalizes false
  alarms and rewards mutation kills.
- **Disable reasoning by default.** These tasks reward correctness over deliberation, and verbose
  chain-of-thought mainly adds latency and parsing risk.

## Iterating on Prompts

To compare prompts, edit `prompts/<track>.md`, run a small slice, and diff the resulting summaries:

```bash
uv run qabench run --track unit_test_gen --models claude-haiku-4-5 --limit 3 --run-id prompt-a
uv run qabench score prompt-a
# edit the prompt, then:
uv run qabench run --track unit_test_gen --models claude-haiku-4-5 --limit 3 --run-id prompt-b
uv run qabench score prompt-b
```

The `prompt_hash` column identifies which prompt produced which rows.
