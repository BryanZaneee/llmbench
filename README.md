# llmbench

```
██╗     ██╗     ███╗   ███╗██████╗ ███████╗███╗   ██╗ ██████╗██╗  ██╗
██║     ██║     ████╗ ████║██╔══██╗██╔════╝████╗  ██║██╔════╝██║  ██║
██║     ██║     ██╔████╔██║██████╔╝█████╗  ██╔██╗ ██║██║     ███████║
██║     ██║     ██║╚██╔╝██║██╔══██╗██╔══╝  ██║╚██╗██║██║     ██╔══██║
███████╗███████╗██║ ╚═╝ ██║██████╔╝███████╗██║ ╚████║╚██████╗██║  ██║
╚══════╝╚══════╝╚═╝     ╚═╝╚═════╝ ╚══════╝╚═╝  ╚═══╝ ╚═════╝╚═╝  ╚═╝
```

**Published LLM leaderboards in your terminal, plus your own benchmarks.**
CLI-first, open source, MIT-licensed.

```bash
llmbench leaderboard --source lmarena --top 10   # published scores, no API key
llmbench config --init                           # one file for every API key
llmbench run suite.cat_bench.yaml --open         # your own run, HTML gallery
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
llmbench config --init     # writes ~/.llmbench/config.yaml
```

Requires Python 3.11+. LMArena needs `pip install llmbench[lmarena]` for pyarrow.

---

## Published leaderboards

Real scores, no API keys, cached for 24h:

| Source        | Provides                                                          |
| ------------- | ----------------------------------------------------------------- |
| `huggingface` | Open LLM Leaderboard v2 (IFEval, BBH, MATH, GPQA, MUSR, MMLU-PRO) |
| `lmarena`     | LMArena ELO from human-preference voting                          |
| `aider`       | Aider Polyglot: multi-language code-editing pass rate             |
| `bundled`     | Snapshot shipped inside the package (works offline)               |

```bash
llmbench leaderboard --source lmarena --top 10
llmbench leaderboard --source huggingface --model llama
llmbench leaderboard --source bundled --offline
llmbench leaderboard --list-sources
```

Every data-returning command takes `--json`:

```bash
llmbench leaderboard --source lmarena --top 20 --json | jq '.entries[].display_name'
```

A GitHub Action refreshes all four daily into `web/data/all.json`, which backs the
sortable table at [bryanzane.com/llmbench](https://bryanzane.com/llmbench). Each
source fetches independently, so one failing upstream costs its rows, not the day.

---

## Configuration

One file, `~/.llmbench/config.yaml`, holds every API key and every model.
`llmbench config --init` writes a commented starter; `llmbench config` shows
what currently resolves and from where.

```yaml
api_keys:
  openai: "sk-..."
  moonshot: "sk-..."

models:
  - { provider: openai,   adapter: openai_compat, model: gpt-4o-mini }
  - { provider: moonshot, adapter: openai_compat, model: kimi-k2.5 }
  - { provider: ollama,   adapter: openai_compat, model: llama3.2 }

benchmarks: [throughput]
repetitions: 3
```

Keys in this file win over environment variables; env vars still work as a
fallback, which is how CI supplies them. Twenty providers are known by name:

| Group  | Providers |
| ------ | --------- |
| Hosted | `openai` `anthropic` `gemini` `moonshot` `deepseek` `xai` `groq` `mistral` `together` `fireworks` `openrouter` `perplexity` `cerebras` `qwen` `nvidia` `nebius` `deepinfra` `sambanova` |
| Image  | `flux` (Black Forest Labs), plus `openai` and `gemini` |
| Local  | `ollama` `vllm` `lmstudio` `llamacpp` (no key needed) |

Each entry in `config.PROVIDERS` carries the accepted environment variable
names and a default base URL. Adding a provider is one row there plus
`adapter: openai_compat` on the model. Where the ecosystem disagrees on a name
(`TOGETHER_API_KEY` vs `TOGETHERAI_API_KEY`, and likewise for Fireworks and
Perplexity), both spellings resolve.

`adapter` is the wire protocol, not the vendor. There are four:
`anthropic`, `openai_compat`, `gemini`, `flux`.

---

## Your own benchmarks

| Benchmark    | Measures                                                          |
| ------------ | ----------------------------------------------------------------- |
| `throughput` | TTFT, tokens/sec, inter-chunk latency, total latency, token usage |
| `image_gen`  | Latency plus saved PNGs for visual review (e.g. `CatBench`)       |

```bash
llmbench run                              # your config models
llmbench run suite.cat_bench.yaml --open  # a suite file, then open the gallery
llmbench view --latest
```

A suite is a YAML file. Omit `models:` to fall back to your config:

```yaml
benchmarks: [image_gen]
prompts_file: prompts/cat_bench.yaml
repetitions: 3
concurrency: 2

models:
  - { provider: openai, adapter: openai_compat, model: dall-e-3, label: "DALL-E 3" }
  - { provider: flux,   adapter: flux,          model: flux-2-klein-4b }
```

A model may narrow which benchmarks it runs with `benchmarks: [image_gen]`.
Pairs the adapter cannot serve are skipped with a warning rather than failing
mid-run.

Output:

```
results/<run_id>/
├── gallery.html            # side-by-side text and image comparison
└── images/<model>/...      # generated PNGs (if image_gen ran)
```

---

## Extending

Subclass `Adapter`, `Benchmark`, or `LeaderboardSource` (see `base.py` in each
directory) and register it in the corresponding `__init__.py`. Most new
providers need no adapter at all: add a row to `config.PROVIDERS` and use
`adapter: openai_compat`.

> Read `history.md` before non-trivial architectural changes. It is the running design log.

---

## Contributing

PRs welcome. Add tests (see `tests/test_*.py`), keep modules single-purpose, and
append a line to `history.md` for design decisions. Run `pytest -q` first.

---

## License

MIT, see [LICENSE](LICENSE).
