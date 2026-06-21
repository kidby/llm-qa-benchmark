# Adding a Model

Add one `[[model]]` table to [`config/models.toml`](../config/models.toml). No code changes are
required.

```toml
[[model]]
slug = "gpt-5-5"                 # unique key, used on the CLI and in every result row
id = "openai/gpt-5.5"            # the provider's model id
provider = "openrouter"          # openrouter | local
label = "GPT-5.5"                # optional, defaults to slug
input_cost_per_mtok = 5.0        # optional, used for cost reporting
output_cost_per_mtok = 30.0
```

A local model has the same shape:

```toml
[[model]]
slug = "qwen3-32b"
id = "qwen3:32b"
provider = "local"
label = "Qwen3 32B"
```

Then run it:

```bash
uv run qabench list-models
uv run qabench run --models gpt-5-5 --track unit_test_gen --limit 3
```

The `provider` field is the only behavioural switch; it selects the generate function. Optional
fields: `context_override`; `skip_by_default`, which excludes a model from `--models all`; and
`params_b`, the disclosed parameter count in billions, shown in `list-models` for size comparison
and omitted for closed models. Most entries set `skip_by_default = true` so `--models all` stays a
fast default set; enable the rest with `--models *` or by slug.

Quantization is not selectable through OpenRouter, which abstracts it as a provider-routing detail.
To benchmark a specific quantization, use the `local` provider against an Ollama or vLLM server and
pin the quantized tag, for example `qwen2.5-coder:32b` or `qwen2.5-coder:32b-instruct-q8_0`.

## Local and Gateway Models

Any OpenAI-compatible endpoint works through the `local` provider. Point `LOCAL_BASE_URL` and
`LOCAL_API_KEY` at a local server such as Ollama or vLLM, or at a hosted gateway such as Vercel AI
Gateway, Groq, or Together, then add a `[[model]]` entry with `provider = "local"`.
