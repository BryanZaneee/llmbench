# llmbench

```
██╗     ██╗     ███╗   ███╗██████╗ ███████╗███╗   ██╗ ██████╗██╗  ██╗
██║     ██║     ████╗ ████║██╔══██╗██╔════╝████╗  ██║██╔════╝██║  ██║
██║     ██║     ██╔████╔██║██████╔╝█████╗  ██╔██╗ ██║██║     ███████║
██║     ██║     ██║╚██╔╝██║██╔══██╗██╔══╝  ██║╚██╗██║██║     ██╔══██║
███████╗███████╗██║ ╚═╝ ██║██████╔╝███████╗██║ ╚████║╚██████╗██║  ██║
╚══════╝╚══════╝╚═╝     ╚═╝╚═════╝ ╚══════╝╚═╝  ╚═══╝ ╚═════╝╚═╝  ╚═╝
```

**Benchmark any AI model — any provider, one command.** CLI-first, open source, MIT-licensed.

```bash
llmbench                                       # interactive TUI
llmbench run suite.example.yaml --open         # run a suite, open HTML gallery
llmbench leaderboard --source lmarena -m claude  # search published scores
```

---

## Table of contents

- [Features](#features)
- [Install](#install)
- [Quick start](#quick-start)
- [The TUI](#the-tui)
- [Running your own benchmarks](#running-your-own-benchmarks)
- [Viewing published leaderboards](#viewing-published-leaderboards)
- [Searching for specific models](#searching-for-specific-models)
- [Supported providers](#supported-providers)
- [Output artifacts](#output-artifacts)
- [Agent-friendly JSON output](#agent-friendly-json-output)
- [Querying results with SQL](#querying-results-with-sql)
- [Extending llmbench](#extending-llmbench)
- [Project layout](#project-layout)
- [Contributing](#contributing)
- [License](#license)

---

## Features

**Local benchmarks** run against any provider you configure:

| Benchmark        | What it measures                                                                      |
| ---------------- | ------------------------------------------------------------------------------------- |
| `throughput`     | TTFT, tokens/sec, inter-chunk latency, total latency, token usage                     |
| `quality_exact`  | Deterministic check against `expected` (exact / contains / regex) — 1.0 or 0.0 score  |
| `quality_judge`  | LLM-as-judge: a judge model scores each output 1–10 with one-line reasoning           |
| `image_gen`      | Latency + saved PNGs at known paths for side-by-side human review                     |

**Published leaderboards** pull real scores from the internet — no API keys required:

| Source          | What it provides                                                                      |
| --------------- | ------------------------------------------------------------------------------------- |
| `huggingface`   | Open LLM Leaderboard v2 — IFEval, BBH, MATH, GPQA, MUSR, MMLU-PRO (OSS models)        |
| `lmarena`       | LMArena ELO ratings from human-preference voting (text, vision, webdev, etc.)         |
| `bundled`       | Snapshot shipped with llmbench — works offline                                         |

**Two interfaces, same engine:**
- **Humans**: interactive TUI with ASCII banner, menu-driven model/benchmark picker, browser gallery.
- **Agents / scripts**: every command takes `--json`, outputs deterministic file paths, works headless.

---

## Install

### Zero-install (once published to PyPI)

```bash
uvx llmbench                    # if you use uv (https://docs.astral.sh/uv/)
pipx run llmbench               # if you use pipx
```

> **Note:** `npx` is Node.js only. `uvx` and `pipx run` are the Python equivalents.

### From source

```bash
git clone https://github.com/<you>/llmbench && cd llmbench
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env            # optional: paste in ANTHROPIC_API_KEY / OPENAI_API_KEY
```

Requires Python 3.11+.

---

## Quick start

Zero setup — see published scores immediately:

```bash
llmbench leaderboard --source lmarena --top 10      # ELO leaderboard
llmbench leaderboard --source huggingface --model llama
llmbench leaderboard --source bundled --offline     # works without internet
```

Your own benchmark run (requires at least one API key *or* a local model like Ollama):

```bash
llmbench run suite.example.yaml --open
```

Or launch the interactive menu:

```bash
llmbench
```

---

## The TUI

Running `llmbench` with no arguments launches an interactive menu:

```
██╗     ██╗     ███╗   ███╗██████╗ ███████╗███╗   ██╗ ██████╗██╗  ██╗
██║     ██║     ████╗ ████║██╔══██╗██╔════╝████╗  ██║██╔════╝██║  ██║
██║     ██║     ██╔████╔██║██████╔╝█████╗  ██╔██╗ ██║██║     ███████║
██║     ██║     ██║╚██╔╝██║██╔══██╗██╔══╝  ██║╚██╗██║██║     ██╔══██║
███████╗███████╗██║ ╚═╝ ██║██████╔╝███████╗██║ ╚████║╚██████╗██║  ██║
╚══════╝╚══════╝╚═╝     ╚═╝╚═════╝ ╚══════╝╚═╝  ╚═══╝ ╚═════╝╚═╝  ╚═╝

  benchmark any AI model · any provider · one command
  API keys: ● Anthropic   ○ OpenAI

? What would you like to do?
  > Run benchmarks
    View published leaderboards
    Configure API keys
    View past results
    Quit
```

Each option opens a guided flow:

- **Run benchmarks** — multi-select models, multi-select benchmarks, choose repetitions, auto-open gallery.
- **View published leaderboards** — pick source, filter by model name, choose row count.
- **Configure API keys** — pick provider, paste key (masked), persisted to `.env`.
- **View past results** — list recent runs, re-open any gallery or print its summary.

---

## Running your own benchmarks

A **suite** is a YAML file listing the models and benchmarks you want to run:

```yaml
benchmarks: [throughput, quality_exact, quality_judge]
prompts_file: prompts/default.yaml
repetitions: 3
concurrency: 2

judge:                                    # used by quality_judge
  provider: anthropic
  adapter: anthropic
  model: claude-opus-4-7

models:
  - provider: anthropic
    adapter: anthropic
    model: claude-opus-4-7
    label: "Claude Opus 4.7"

  - provider: openai
    adapter: openai
    model: gpt-4o-mini

  - provider: ollama
    adapter: ollama
    model: llama3.2
```

Run it:

```bash
llmbench run my-suite.yaml --open
```

You get a Rich results table in the terminal plus artifacts on disk (see [Output artifacts](#output-artifacts)).

### Adding a model

Paste the right block into the `models:` list:

```yaml
# Claude
- { provider: anthropic, adapter: anthropic, model: claude-opus-4-7 }

# OpenAI
- { provider: openai, adapter: openai, model: gpt-4o-mini }

# OpenAI image-gen
- { provider: openai, adapter: openai, model: gpt-image-1, benchmarks: [image_gen] }

# Local Ollama
- { provider: ollama, adapter: ollama, model: llama3.2 }

# Local vLLM
- { provider: vllm, adapter: vllm, model: meta-llama/Llama-3.1-8B-Instruct }

# Any OpenAI-compatible server (LM Studio, llama.cpp, TGI, custom gateway)
- { provider: my-gateway, adapter: openai_compat, model: whatever-id, base_url: http://gateway.internal/v1 }
```

The optional `benchmarks: [...]` field restricts which benchmarks run against a specific model. Useful for image-only or text-only models.

### Prompts

Prompts are YAML records. The optional `expected` and `rubric` fields enable quality benchmarks:

```yaml
- id: bat_ball
  prompt: "A bat and a ball cost $1.10..."
  expected: "5 cents"              # quality_exact: substring/exact/regex match
  check: contains
  rubric: "Score 1-10 on reasoning clarity and correctness."  # quality_judge

- id: img_cat
  prompt: "A photorealistic tabby cat on a red wool rug."
  # no expected/rubric — image_gen and throughput use this, quality_* skip it
```

---

## Viewing published leaderboards

No API keys, no model downloads, no runs — just published scores:

```bash
llmbench leaderboard                               # HuggingFace top 20
llmbench leaderboard --source lmarena --top 10     # LMArena ELO
llmbench leaderboard --source bundled              # offline snapshot
llmbench leaderboard --list-sources                # see all sources
```

Data is cached at `~/.cache/llmbench/leaderboards/<source>.json` with a 24-hour TTL. Use `--refresh` to bypass the cache, `--offline` to skip network entirely.

> **Important:** published numbers are not directly comparable to local benchmark results. They're measured in different environments with different prompts. Use them as context, not ground truth for your setup.

---

## Searching for specific models

Both the CLI and TUI let you filter leaderboards by model name (case-insensitive substring match on display name or model ID):

```bash
llmbench leaderboard --model claude                # all claude variants
llmbench leaderboard --model "gpt-5" --source lmarena
llmbench leaderboard --model llama --source huggingface
llmbench leaderboard -m haiku -s lmarena -n 5      # short flags
```

Example output:

```
$ llmbench leaderboard --source lmarena --model claude --top 5
┏━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━┓
┃ #   ┃ Model                    ┃ Org       ┃     elo ┃
┡━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━┩
│ 1   │ claude-opus-4-6-thinking │ anthropic │ 1499.92 │
│ 2   │ claude-opus-4-6          │ anthropic │ 1494.97 │
│ 3   │ claude-opus-4-7-thinking │ anthropic │ 1487.18 │
│ 4   │ claude-opus-4-7          │ anthropic │ 1480.57 │
│ 5   │ claude-opus-4-5-20251101 │ anthropic │ 1448.53 │
└─────┴──────────────────────────┴───────────┴─────────┘
```

In the TUI, the "View published leaderboards" flow prompts for a filter string.

---

## Supported providers

| Adapter         | Targets                                                    |
| --------------- | ---------------------------------------------------------- |
| `anthropic`     | Claude API (Opus / Sonnet / Haiku). Text.                  |
| `openai`        | OpenAI API (GPT-4o, o-series, dall-e-3, gpt-image-1, ...). |
| `ollama`        | Local Ollama server. Text.                                 |
| `vllm`          | Local vLLM server. Text.                                   |
| `lmstudio`      | LM Studio local server. Text.                              |
| `openai_compat` | Any OpenAI-compatible endpoint (text + optional images).   |

The same benchmarks run unchanged against a 1B model on your laptop and Claude Opus through the API — the runner doesn't care.

---

## Output artifacts

After `llmbench run`, a fresh `results/` looks like:

```
results/
├── results.db                        # SQLite, one row per (model, prompt, repetition)
├── <run_id>.jsonl                    # full pydantic dump of every result
└── <run_id>/
    ├── gallery.html                  # side-by-side text + image comparison
    └── images/<model_slug>/
        └── <prompt_id>__rep0.png     # generated images (if image_gen ran)
```

Open the gallery anytime:

```bash
llmbench view <run_id>      # or --latest
```

---

## Agent-friendly JSON output

Every data-returning command accepts `--json`:

```bash
llmbench run suite.yaml --json > run.json
llmbench leaderboard --source lmarena --top 20 --json | jq '.entries[].display_name'
```

No Rich table, no escape codes. A single JSON document on stdout, ready to pipe into `jq`, parse in any language, or return from a tool-use call.

---

## Querying results with SQL

```sql
-- Top-line numbers per model
SELECT provider||'/'||model AS model,
       ROUND(AVG(tokens_per_second), 1) AS tok_s,
       ROUND(AVG(ttft_ms), 0) AS ttft_ms,
       ROUND(AVG(score), 2) AS avg_score
FROM results
WHERE success = 1
GROUP BY provider, model
ORDER BY avg_score DESC NULLS LAST;
```

```sql
-- Every model's answer to one prompt, with judge reasoning
SELECT provider||'/'||model AS model,
       score,
       json_extract(payload_json, '$.score_reasoning') AS reasoning,
       substr(json_extract(payload_json, '$.sample_output'), 1, 200) AS preview
FROM results
WHERE json_extract(payload_json, '$.prompt_id') = 'bat_ball'
  AND benchmark = 'quality_judge';
```

---

## Extending llmbench

### Add a provider adapter

Create `src/llmbench/adapters/my_provider.py`:

```python
from .base import Adapter, StreamedGeneration

class MyProviderAdapter(Adapter):
    async def stream_generate(self, prompt, *, max_tokens, temperature, top_p):
        ...  # stream from your SDK, return a StreamedGeneration
```

Register it in `src/llmbench/adapters/__init__.py`, then use `adapter: myprovider` in your suite YAML.

### Add a benchmark

Create `src/llmbench/benchmarks/my_bench.py` subclassing `Benchmark` with a `run()` method that returns `list[BenchmarkResult]`. Register it in `src/llmbench/benchmarks/__init__.py`.

### Add a leaderboard source

Create `src/llmbench/leaderboards/my_source.py` subclassing `LeaderboardSource`. Implement `fetch() -> LeaderboardSnapshot`. Register in `src/llmbench/leaderboards/__init__.py`.

---

## Project layout

```
llmbench/
├── pyproject.toml
├── README.md
├── LICENSE                  ← MIT
├── history.md               ← design-decision log, read before big changes
├── suite.example.yaml
├── prompts/default.yaml
├── src/llmbench/
│   ├── schema.py            ← pydantic data shapes
│   ├── config.py            ← YAML + .env loader
│   ├── runner.py            ← async orchestrator
│   ├── storage.py           ← SQLite + JSONL
│   ├── cli.py               ← typer CLI
│   ├── tui.py               ← interactive menu
│   ├── adapters/            ← per-provider glue
│   ├── benchmarks/          ← throughput, quality_exact, quality_judge, image_gen
│   ├── leaderboards/        ← huggingface, lmarena, bundled + cache
│   ├── reports/             ← HTML gallery renderer
│   └── data/                ← bundled leaderboard snapshot
└── tests/
```

---

## Contributing

Contributions welcome. The fastest paths to useful PRs:

- **New adapters** (Cohere, Mistral, Bedrock, Vertex, …) — ~40 lines each, see the `Adapter` contract in `src/llmbench/adapters/base.py`.
- **New benchmarks** — cost-per-1k-tokens, streaming stability, long-context recall, etc.
- **New leaderboard sources** — any public API with per-model scores.

Ground rules:
- Keep modules short and single-purpose. When in doubt, favor clarity over cleverness.
- Add tests for new benchmarks and adapters (see `tests/test_*.py` for patterns).
- Update `history.md` with your design rationale — it's the project's running architecture log.
- No heavy dependencies without a strong reason; we aim to stay slim.

Run the full suite before opening a PR:

```bash
pytest -q
```

---

## License

MIT — see [LICENSE](LICENSE).
