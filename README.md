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
llmbench                                         # interactive TUI
llmbench task file-refactor                      # run a sandboxed agentic task
llmbench run suite.example.yaml --open           # run a benchmark suite, open the HTML gallery
llmbench leaderboard --source lmarena -m claude  # search published scores
```

---

## Install

```bash
pip install llmbench       # standard
uvx llmbench               # zero-install (uv)
pipx run llmbench          # zero-install (pipx)
```

From source:

```bash
git clone https://github.com/BryanZaneee/llmbench && cd llmbench
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env       # paste in ANTHROPIC_API_KEY / OPENAI_API_KEY
```

Requires Python 3.11+.

---

## What it does

**Local benchmarks** — run against any provider you configure:

| Benchmark        | Measures                                                          |
| ---------------- | ----------------------------------------------------------------- |
| `throughput`     | TTFT, tokens/sec, inter-chunk latency, total latency, token usage |
| `quality_exact`  | Deterministic check vs `expected` (exact / contains / regex)      |
| `quality_judge`  | LLM-as-judge: 1–10 score with one-line reasoning                  |
| `image_gen`      | Latency + saved PNGs for side-by-side review                      |

**Published leaderboards** — real scores without needing any API keys:

| Source        | Provides                                                          |
| ------------- | ----------------------------------------------------------------- |
| `huggingface` | Open LLM Leaderboard v2 (IFEval, BBH, MATH, GPQA, MUSR, MMLU-PRO) |
| `lmarena`     | LMArena ELO from human-preference voting                          |
| `aider`       | Aider Polyglot — multi-language code-editing pass rate            |
| `bundled`     | Snapshot shipped with llmbench (works offline)                    |

**Agentic tasks** drive an LLM agent through a multi-step scenario in a sealed sandbox. Verdict is computed from post-run state, not text:

| Task                  | What it tests                                                                |
| --------------------- | ---------------------------------------------------------------------------- |
| `file-refactor`       | Rename a function across a 5-file mock project without breaking parsing.     |
| `api-orchestration`   | GET a list, transform each row, POST to an audit endpoint with a field rename. |
| `multi-step-research` | Synthesize four canned search results into a markdown brief.                 |
| `recovery`            | Retry a transient transactional failure and verify the side effect landed.   |
| `long-horizon`        | Parse a config, fetch sources, and write a multi-section report (~15 steps). |

Every task run produces a `TraceDocument` JSON at `runs/<run_id>.json` capturing every turn, tool call, token count, timing, cost, and verdict. Browse them via the TUI's "View past task traces" flow. Agent providers: `anthropic`, `openai`, `gemini`, `moonshot`. See `llmbench list-tasks` and `llmbench list-models` (with priced rates) for the catalog.

---

## Quick start

Zero setup — see published scores immediately:

```bash
llmbench leaderboard --source lmarena --top 10
llmbench leaderboard --source huggingface --model llama
llmbench leaderboard --source bundled --offline
```

Run your own benchmark (needs at least one API key, or a local model):

```bash
llmbench run suite.example.yaml --open
```

Run an agentic task:

```bash
llmbench task file-refactor                          # default model, one repetition
llmbench task long-horizon --provider openai -m gpt-4o --reps 3
llmbench list-tasks                                  # see all registered tasks
llmbench list-models                                 # priced model catalog
```

Or launch the menu:

```bash
llmbench
```

---

## Suites

A suite is a YAML file listing models and benchmarks:

```yaml
benchmarks: [throughput, quality_exact, quality_judge]
prompts_file: prompts/default.yaml
repetitions: 3
concurrency: 2

judge:
  provider: anthropic
  adapter: anthropic
  model: claude-opus-4-7

models:
  - { provider: anthropic, adapter: anthropic, model: claude-opus-4-7 }
  - { provider: openai,    adapter: openai,    model: gpt-4o-mini }
  - { provider: ollama,    adapter: ollama,    model: llama3.2 }
  - { provider: openai,    adapter: openai,    model: gpt-image-1, benchmarks: [image_gen] }
  - { provider: gw, adapter: openai_compat, model: x, base_url: http://gateway.internal/v1 }
```

Prompts are YAML records; optional `expected` / `rubric` fields enable the quality benchmarks. See `prompts/default.yaml` for examples.

---

## Supported providers

| Adapter         | Targets                                                  |
| --------------- | -------------------------------------------------------- |
| `anthropic`     | Claude API (Opus / Sonnet / Haiku).                      |
| `openai`        | OpenAI API (GPT-4o, o-series, dall-e-3, gpt-image-1).    |
| `ollama`        | Local Ollama server.                                     |
| `vllm`          | Local vLLM server.                                       |
| `lmstudio`      | LM Studio local server.                                  |
| `openai_compat` | Any OpenAI-compatible endpoint (text + optional images). |

---

## Output

After `llmbench run`:

```
results/
├── results.db                  # SQLite, one row per (model, prompt, repetition)
└── <run_id>/
    ├── gallery.html            # side-by-side text + image comparison
    └── images/<model>/...      # generated PNGs (if image_gen ran)
```

Re-open later with `llmbench view <run_id>` (or `--latest`). Every `BenchmarkResult` is also stored as a JSON blob in the SQLite `payload_json` column; query it with `json_extract` for ad-hoc analysis.

After `llmbench task`:

```
runs/
└── <run_id>.json               # one TraceDocument per repetition (steps, tool calls, totals, verdict)
```

Inspect a trace with the TUI's "View past task traces" flow, or load `runs/<run_id>.json` directly; its shape is the `TraceDocument` pydantic model in `schema.py`.

Every data-returning command takes `--json` for piping into `jq` or tool-use:

```bash
llmbench leaderboard --source lmarena --top 20 --json | jq '.entries[].display_name'
```

---

## Extending

Subclass `Adapter`, `Benchmark`, or `LeaderboardSource` (see `base.py` in each directory) and register your class in the corresponding `__init__.py`. New adapters are typically ~40 lines.

> Read `history.md` before non-trivial architectural changes — it's the running design log.

---

## Contributing

PRs welcome. Add tests (see `tests/test_*.py` for patterns), keep modules single-purpose, and append a line to `history.md` for design decisions. Run `pytest -q` before opening a PR.

---

## License

MIT — see [LICENSE](LICENSE).
