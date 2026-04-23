# benchman

```
██████╗ ███████╗███╗   ██╗ ██████╗██╗  ██╗███╗   ███╗ █████╗ ███╗   ██╗
██╔══██╗██╔════╝████╗  ██║██╔════╝██║  ██║████╗ ████║██╔══██╗████╗  ██║
██████╔╝█████╗  ██╔██╗ ██║██║     ███████║██╔████╔██║███████║██╔██╗ ██║
██╔══██╗██╔══╝  ██║╚██╗██║██║     ██╔══██║██║╚██╔╝██║██╔══██║██║╚██╗██║
██████╔╝███████╗██║ ╚████║╚██████╗██║  ██║██║ ╚═╝ ██║██║  ██║██║ ╚████║
╚═════╝ ╚══════╝╚═╝  ╚═══╝ ╚═════╝╚═╝  ╚═╝╚═╝     ╚═╝╚═╝  ╚═╝╚═╝  ╚═══╝
```

**Benchmark any AI model — any provider, one command.**

Drop in a model (Claude, OpenAI, Ollama, vLLM, LM Studio, or any OpenAI-compatible endpoint), run one command, and get back timing metrics, quality scores, and side-by-side generated images / text outputs for human review.

Designed for both humans and agents:
- **Humans** get an interactive TUI with an ASCII banner, menu-driven model/benchmark selection, and a browser-opened HTML gallery for side-by-side review.
- **Agents** get deterministic subcommands with `--json` output, predictable file paths for generated images, and SQLite / JSONL artifacts for downstream analysis.

---

## What you can benchmark

### Local benchmarks (run against live models)

| Benchmark        | What it measures                                                                      |
| ---------------- | ------------------------------------------------------------------------------------- |
| `throughput`     | TTFT, tokens/sec, inter-chunk latency, total latency, token usage                     |
| `quality_exact`  | Deterministic check against `expected` (exact / contains / regex) — 1.0 or 0.0 score  |
| `quality_judge`  | LLM-as-judge: judge model scores the output 1–10 with a short reason                  |
| `image_gen`      | Latency + saved PNGs at known paths for side-by-side human review                     |

### Published leaderboards (no API keys needed)

| Source          | What it provides                                                                      |
| --------------- | ------------------------------------------------------------------------------------- |
| `huggingface`   | Open LLM Leaderboard v2 — IFEval, BBH, MATH, GPQA, MUSR, MMLU-PRO for OSS models      |
| `lmarena`       | LMArena ELO ratings from human-preference voting (text, vision, webdev, etc.)         |
| `bundled`       | A snapshot shipped with benchman — works offline, may be stale                        |

```bash
benchman leaderboard                          # huggingface (default), top 20
benchman leaderboard --source lmarena         # ELO ratings
benchman leaderboard --source bundled         # offline snapshot
benchman leaderboard --model claude           # filter by model name
benchman leaderboard --refresh                # force a re-fetch
benchman leaderboard --offline                # cache/bundle only
benchman leaderboard --json                   # for agents / piping to jq
```

Results are cached at `~/.cache/benchman/leaderboards/<source>.json` with a 24-hour TTL.

**These numbers are not directly comparable to local benchmark results** — they're measured in different environments, with different prompts and scoring methodologies. Use them as context, not ground truth for your setup.

---

## Install & run

### Zero-install (when published to PyPI)

```bash
uvx benchman                    # if you use uv (https://docs.astral.sh/uv/)
pipx run benchman               # if you use pipx
```

These are the Python equivalents of `npx` — they fetch the package, run it, no persistent install. Note: `npx` itself is Node.js only and won't work here.

### Local development

```bash
git clone <this-repo> && cd benchman
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env            # paste in ANTHROPIC_API_KEY / OPENAI_API_KEY

benchman                        # launch interactive TUI
```

### Two ways to use benchman

```bash
benchman                                # interactive TUI (human mode)
benchman run suite.example.yaml --open  # direct command (scripts, CI, agents)
```

Both share the same guts — the TUI is just a menu-driven wrapper over the subcommands.

After a run you'll have:
- `results/results.db` — SQLite, one row per (model, prompt, repetition).
- `results/<run_id>.jsonl` — full pydantic dump of every result.
- `results/<run_id>/gallery.html` — side-by-side text + image comparison (auto-opens with `--open`).
- `results/<run_id>/images/<model>/<prompt_id>__rep0.png` — generated images (if `image_gen` ran).

---

## CLI reference

```bash
benchman                                     # interactive TUI
benchman run <suite.yaml> [--out DIR] [--open] [--json]
benchman view <run_id>    [--out DIR]        # open gallery for a past run
benchman view --latest                       # open the most recent gallery
benchman list-runs        [--limit N]        # recent run IDs
benchman list-adapters                       # supported provider adapters
benchman list-benchmarks                     # registered benchmarks
benchman leaderboard [--source ...] [--model ...] [--top N] [--refresh|--offline] [--json]
```

### The interactive TUI

```bash
$ benchman
```

```
██████╗ ███████╗███╗   ██╗ ██████╗██╗  ██╗███╗   ███╗ █████╗ ███╗   ██╗
██╔══██╗██╔════╝████╗  ██║██╔════╝██║  ██║████╗ ████║██╔══██╗████╗  ██║
██████╔╝█████╗  ██╔██╗ ██║██║     ███████║██╔████╔██║███████║██╔██╗ ██║
██╔══██╗██╔══╝  ██║╚██╗██║██║     ██╔══██║██║╚██╔╝██║██╔══██║██║╚██╗██║
██████╔╝███████╗██║ ╚████║╚██████╗██║  ██║██║ ╚═╝ ██║██║  ██║██║ ╚████║
╚═════╝ ╚══════╝╚═╝  ╚═══╝ ╚═════╝╚═╝  ╚═╝╚═╝     ╚═╝╚═╝  ╚═╝╚═╝  ╚═══╝

  benchmark any AI model · any provider · one command
  API keys: ● Anthropic   ○ OpenAI

? What would you like to do?
  > Run benchmarks
    Configure API keys
    View past results
    Quit
```

- **Run benchmarks** → choose a preset suite / load a YAML / build one interactively (multi-select models, multi-select benchmarks, choose repetitions).
- **Configure API keys** → pick a provider, enter the key, it's persisted to `.env`.
- **View past results** → pick a past run, open its gallery or print its summary.

### Agent-friendly output

```bash
benchman run suite.yaml --json > results.json
```

Emits a single JSON document on stdout:
```json
{
  "run_id": "ab12...",
  "gallery": "results/ab12.../gallery.html",
  "results": [ {...}, {...} ]
}
```

No Rich table, no terminal noise — pipe-able into `jq` or any agent's tool-use payload.

---

## How it works

```
          suite.yaml
              │
              ▼
  ┌────────────────────────┐
  │   cli.py   (typer)     │   you enter here
  └──────────┬─────────────┘
             │
             ▼
  ┌────────────────────────┐
  │   runner.py            │   fans out every (model, benchmark)
  │   asyncio + semaphore  │   pair, capped by `concurrency`
  └──────────┬─────────────┘
             │
       ┌─────┴─────┐
       ▼           ▼
  ┌─────────┐  ┌──────────────┐
  │adapters/│  │ benchmarks/  │
  │provider │  │  metrics     │
  │  glue   │  │              │
  └────┬────┘  └──────┬───────┘
       │              │
       └──────┬───────┘
              ▼
  ┌─────────────────────────┐
  │ storage.py (DB + JSONL) │
  │ reports/html.py         │
  └─────────────────────────┘
```

### Flow in plain terms

1. **You write a YAML** listing models, benchmarks, and a judge (optional).
2. **`runner.py`** builds a grid of `(model, benchmark)` tasks and runs them in parallel under a `concurrency` semaphore.
3. Each task picks an **adapter** (Claude, OpenAI, Ollama, …) and a **benchmark** (throughput, quality, image_gen) and calls it.
4. Results go to SQLite + JSONL + a self-contained HTML gallery.

---

## Adding a model

Paste a block into your suite YAML.

### Claude (Anthropic API)

```yaml
- provider: anthropic
  adapter: anthropic
  model: claude-opus-4-7
  label: "Opus 4.7"
```

### OpenAI

```yaml
- provider: openai
  adapter: openai
  model: gpt-4o-mini
```

### Local OSS model via Ollama

```bash
ollama serve && ollama pull llama3.2
```

```yaml
- provider: ollama
  adapter: ollama
  model: llama3.2
```

### Local model via vLLM

```yaml
- provider: vllm
  adapter: vllm
  model: meta-llama/Llama-3.1-8B-Instruct
  base_url: http://localhost:8000/v1    # optional; else VLLM_BASE_URL is used
```

### Image-gen model (OpenAI)

```yaml
- provider: openai
  adapter: openai
  model: gpt-image-1
  label: "GPT Image 1"
  benchmarks: [image_gen]              # restrict to just image_gen
```

### Anything OpenAI-chat-compatible (llama.cpp, TGI, custom gateways)

```yaml
- provider: my-gateway
  adapter: openai_compat
  model: whatever-id-your-server-returns
  base_url: http://gateway.internal/v1
```

### Per-model benchmark filter

Each `models[]` entry may include `benchmarks: [name, ...]` to restrict which benchmarks run against it. Useful for image-only or text-only models. Omit the field to run every top-level benchmark.

---

## Prompts

Prompts are YAML records; the new fields `expected`, `check`, and `rubric` opt into quality benchmarks.

```yaml
- id: bat_ball
  prompt: "A bat and a ball cost $1.10..."
  expected: "5 cents"
  check: contains           # exact | contains | regex     (default: contains)
  rubric: "Score 1-10 on reasoning clarity and correctness of the final answer."

- id: img_cat
  prompt: "A photorealistic tabby cat on a red wool rug."
  # no expected/rubric — used only by image_gen and throughput
```

Benchmarks self-filter:
- `quality_exact` only runs on prompts with `expected`.
- `quality_judge` runs on all prompts; uses `rubric` if present, else a generic rubric.
- `image_gen` uses every prompt's text.
- `throughput` runs on every prompt.

---

## Quality evaluation

### Deterministic (`quality_exact`)

For prompts with known answers (math, factual Qs, presence of a keyword). Zero cost, fully reproducible.

### LLM-as-judge (`quality_judge`)

For subjective quality (writing, reasoning, code review). Uses a second model — configured at suite level:

```yaml
judge:
  provider: anthropic
  adapter: anthropic
  model: claude-opus-4-7
```

If omitted, defaults to Claude Opus 4.7 (requires `ANTHROPIC_API_KEY`).

The judge gets the prompt, the model's response, and the prompt-specific rubric (or a generic one) and returns:

```json
{"score": 8, "reasoning": "Answer is correct, reasoning is clear, missed edge case."}
```

Scores and reasoning are stored on every `BenchmarkResult` and rendered in the gallery.

---

## Image generation

Image gen is a first-class benchmark. The workflow:

1. `image_gen` calls `adapter.generate_image(prompt)` — currently implemented on `OpenAICompatAdapter`, so it works with any OpenAI-compatible images endpoint (OpenAI's own API, or a local SD server behind an OpenAI-compat shim).
2. PNGs are written to deterministic paths: `results/<run_id>/images/<model_slug>/<prompt_id>__rep<N>.png`.
3. Metrics (latency, size) go into the normal `BenchmarkResult` schema.
4. The gallery renders them side by side, one row per prompt, one column per model.

**Viewing:** the run command with `--open` auto-launches the gallery in your default browser. `benchman view <run_id>` (or `--latest`) re-opens it anytime.

---

## Querying results (SQL)

```bash
# Top-line numbers per model:
sqlite3 results/results.db "
  SELECT provider||'/'||model AS model,
         ROUND(AVG(tokens_per_second), 1) AS tok_s,
         ROUND(AVG(ttft_ms), 0)          AS ttft_ms,
         ROUND(AVG(score), 2)            AS avg_score,
         COUNT(*)                        AS n
  FROM results
  WHERE success = 1
  GROUP BY provider, model
  ORDER BY avg_score DESC NULLS LAST, tok_s DESC;
"
```

```bash
# Every model's answer to a specific prompt, plus judge score + reasoning:
sqlite3 results/results.db "
  SELECT provider||'/'||model AS model,
         score,
         json_extract(payload_json, '$.score_reasoning') AS reasoning,
         substr(json_extract(payload_json, '$.sample_output'), 1, 200) AS preview
  FROM results
  WHERE json_extract(payload_json, '$.prompt_id') = 'bat_ball'
    AND benchmark = 'quality_judge';
"
```

---

## Config reference

### Suite YAML

```yaml
benchmarks: [throughput, quality_exact, quality_judge, image_gen]
prompts_file: prompts/default.yaml
repetitions: 3
concurrency: 2
results_dir: results
sampling:
  max_tokens: 512
  temperature: 0.0
  top_p: 1.0
judge:                       # optional; defaults to Claude Opus 4.7
  provider: anthropic
  adapter: anthropic
  model: claude-opus-4-7
models:
  - provider: ...
    adapter: ...
    model: ...
    label: ...               # optional display name
    base_url: ...            # optional; overrides env-var defaults
    benchmarks: [...]        # optional; restricts which benchmarks run on this model
```

### Environment variables (`.env`)

```
ANTHROPIC_API_KEY=
OPENAI_API_KEY=
OLLAMA_BASE_URL=http://localhost:11434/v1
VLLM_BASE_URL=http://localhost:8000/v1
LMSTUDIO_BASE_URL=http://localhost:1234/v1
```

---

## Supported adapters

| Adapter         | Targets                                                    |
| --------------- | ---------------------------------------------------------- |
| `anthropic`     | Claude API (Opus / Sonnet / Haiku). Text only.             |
| `openai`        | OpenAI API (GPT-4o, o-series, dall-e-3, gpt-image-1, ...)  |
| `ollama`        | Local Ollama server. Text only.                            |
| `vllm`          | Local vLLM server. Text only (vLLM doesn't do image gen).  |
| `lmstudio`      | LM Studio local server. Text only.                         |
| `openai_compat` | Any OpenAI-compatible endpoint (text + optional image gen) |

---

## Extending

### Add a new adapter (non-OpenAI-compatible provider)

1. Create `src/benchman/adapters/my_provider.py`:
   ```python
   from .base import Adapter, StreamedGeneration

   class MyProviderAdapter(Adapter):
       async def stream_generate(self, prompt, *, max_tokens, temperature, top_p):
           ...  # stream from your SDK, return StreamedGeneration
   ```
2. Register in `src/benchman/adapters/__init__.py`.
3. Reference as `adapter: myprovider` in your suite YAML.

### Add a new benchmark

1. Create `src/benchman/benchmarks/my_bench.py` subclassing `Benchmark` with a `run()` method that returns `list[BenchmarkResult]`.
2. Register in `src/benchman/benchmarks/__init__.py`.
3. Add the name to `benchmarks:` in your suite YAML.

---

## Layout

```
benchman-suite/
├── pyproject.toml
├── README.md
├── history.md               ← design-decision log, read before big changes
├── suite.example.yaml
├── prompts/
│   └── default.yaml
├── src/benchman/
│   ├── schema.py            ← pydantic data shapes (Prompt, BenchmarkResult, ...)
│   ├── config.py            ← YAML + .env loader
│   ├── runner.py            ← async orchestrator
│   ├── storage.py           ← SQLite + JSONL
│   ├── cli.py               ← typer CLI
│   ├── adapters/            ← per-provider glue
│   ├── benchmarks/          ← throughput, quality_exact, quality_judge, image_gen
│   └── reports/             ← HTML gallery renderer
└── tests/
```

---

## Fairness notes

- **Pin judge model version.** LLM-as-judge scores drift when the judge is upgraded. Record the judge in the manifest (done automatically) and pin it explicitly in your suite.
- **Temperature 0 for judging.** The default `quality_judge` call uses `temperature=0.0` for reproducibility. Change only if you know you want it.
- **Warm up before measuring.** First request often pays cold-start cost. `repetitions: 3` is usually enough; discard the first in aggregation if you care.
- **Providers count tokens differently** (tiktoken vs SentencePiece vs custom BPE). Reported token counts are the provider's own numbers.
