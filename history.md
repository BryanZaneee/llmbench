# History

Running log of design and architecture decisions. One line per entry — the "why" goes here, the "what" is in the code. Newest dates at top.

Agents reading this should skim before touching the code: many choices below are deliberate and look non-obvious from the source alone.

## 2026-04-24 — Two-surface distribution (PyPI + bryanzane.com/llmbench)

- Split distribution into two surfaces for two audiences. CLI via PyPI (`uvx llmbench` / `pipx run llmbench`) serves developers who want to run benchmarks. A static page at `bryanzane.com/llmbench` serves non-devs who just want to browse published leaderboards — no terminal, no install. Premise: the value proposition differs by audience; one channel can't do both well.
- Web code lives in `web/` of this repo rather than a separate `llmbench-web` project. Reason: keeps one star count, one issue tracker, one README, and the Python CLI stays the single source of truth for data (web consumes `llmbench leaderboard --json` output directly, shape already matches `LeaderboardSnapshot` in `src/llmbench/leaderboards/base.py`).
- Web stack is plain HTML + CSS + JS with Tailwind + GSAP via CDN, matching `bryanzane_v3/` conventions exactly. No framework, no build step. Rationale: the portfolio site it's embedded in has no build pipeline either; introducing Next.js/Vite here would be the only built asset on the VPS and would clash visually. Uniform stack > "impressive" stack.
- Typography + palette mirror `bryanzane_v3/styles.css` (Source Serif 4, Inter Tight, JetBrains Mono; off-white paper + deep navy ink + voltage blues). The llmbench subpage should read as part of the portfolio, not a bolted-on microsite.
- VPS deployment reuses the existing webhook pattern — VPS clones `llmbench` to `/opt/llmbench/`, Caddy serves `/llmbench/` from `/opt/llmbench/web/` via a `handle_path /llmbench/*` block inside the existing `bryanzane.com` site, push-to-main triggers `git pull` on the VPS. No Python needed on the VPS; the leaderboard JSON snapshots are refreshed by a GitHub Action on daily cron, not by the VPS.
- `.env.example` was **not** added in this pass — it already existed at the repo root from the initial commit. An earlier draft of this plan was wrong about this.
- PyPI publish automated via `.github/workflows/release.yml` triggered on `v*` tag push. First publish still must be done locally (`uv build && uv publish`) to claim the name; after that the workflow handles subsequent releases on each version bump.

## 2026-04-23 — Rename `benchman` -> `llmbench`

- Renamed the project, PyPI package, Python package, and CLI command from `benchman` to `llmbench`. Reason: `benchman` was already taken on PyPI by an unrelated micro-benchmarks tool; `llmbench` is free, cleaner, and more discoverable for the LLM-benchmarking use case. One name all the way down (package, CLI, repo) to avoid the `ai-benchman -> benchman` split-brain pattern.
- Regenerated the ANSI Shadow banner for "LLMBENCH" via pyfiglet (one-shot at dev time — no runtime dep added). Banner now matches the tool name.
- Perl-based bulk rename: `find src tests -name "*.py" -exec perl -pi -e 's/\bbenchman\b/llmbench/g'` plus manual `pyproject.toml`, `README.md`, and `tui.py` banner updates.
- Cache dir naturally follows: `~/.cache/llmbench/leaderboards/<source>.json` (was `~/.cache/benchman/...`). Users refreshing an old install will see a fresh empty cache.
- **Repo directory on disk is still `ai-eval-suite/`** for now — renamed with a one-liner (`mv ai-eval-suite llmbench`). GitHub repo rename via `gh repo rename llmbench` or Settings page.

## 2026-04-23 — Open-source polish + TUI filter

- Added a model-name filter step to the TUI leaderboard flow so humans can narrow by "claude" or "llama" without dropping to CLI flags. Same case-insensitive substring semantics as the CLI `--model` flag — one implementation, two surfaces.
- Added MIT `LICENSE`. Classifiers, keywords, and author metadata added to `pyproject.toml` for PyPI readiness.
- Initialized the git repo and made the initial comprehensive commit. Going forward, changes are committed in small logical groups (one feature / fix per commit) rather than batched.
- README rewritten for open-source scannability: table of contents up top, one-sentence pitch, one-command quick-start (leaderboard works with zero setup), Features section with two clean tables (local benchmarks vs published leaderboards), dedicated "Searching for specific models" section since that was an easily-missed feature. Contributing + License sections at the bottom follow standard OSS conventions.
- Did not retroactively split the initial commit — not worth the history revision for a v0.1.0 bootstrap.

## 2026-04-23 — Published leaderboards

- Added `benchman leaderboard` command + a new `leaderboards/` module with pluggable sources. Motivation: let users see published benchmark numbers without running any local benchmarks (no API keys, no cost).
- Three sources shipped: `huggingface` (Open LLM Leaderboard v2, live JSON from HF datasets-server), `lmarena` (Arena ELO ratings, live parquet download + pyarrow), `bundled` (static snapshot that works offline). Artificial Analysis deliberately skipped — verified they have no public API, and scraping their site risks ToS violations.
- Unified shape via `LeaderboardEntry` with a free-form `metrics: dict[str, float]` — each source publishes different columns (MMLU, ELO, HumanEval, …) so a flexible dict avoids forcing every source into a single metric schema.
- Cache layer at `~/.cache/benchman/leaderboards/<source>.json` with 24-hour TTL. `--refresh` bypasses the cache, `--offline` skips network entirely. `XDG_CACHE_HOME` respected for test isolation.
- Bundled snapshot (`src/benchman/data/bundled_leaderboard.json`) is pre-fetched from HF at build time, not hand-curated — avoids hallucinated numbers and gives real data on first run without network. Included in the wheel via hatch `force-include`.
- LMArena dedup: the `latest` parquet actually contains multiple dated snapshots per model. We group by model_name and keep the most recent publish_date, then re-rank by ELO so the `rank` column is meaningful across the deduped view (not a per-snapshot artifact).
- `pyarrow` added as a dependency (only used by LMArena). Hefty but the standard tool for parquet — `datasets-server` JSON API returned 500 for the LMArena dataset, so we had no cleaner alternative.
- Test isolation for the HTTP fetcher: had to capture `httpx.Client` before patching (otherwise the monkeypatched lambda recurses when it calls `httpx.Client(transport=...)`). Noted for future mocks of `httpx`.
- TUI got a fourth menu entry ("View published leaderboards") reusing the same cache + source registry — no duplicate logic between CLI and TUI paths.
- Explicitly documented that published numbers and locally-measured numbers aren't directly comparable — different environments, different prompts, different scoring. Kept them in separate commands (`leaderboard` vs `run`) rather than mixed in one table.

## 2026-04-23 — Rebrand to `benchman` + interactive TUI

- Renamed package `ai_eval` -> `benchman` and CLI script `ai-eval` -> `benchman`. Project directory stays `ai-eval-suite/` for now; it's a filesystem label, separate from the Python package identity. Rename manually if desired.
- Added interactive TUI (`tui.py`), launched when `benchman` is invoked with no subcommand. Uses a typer callback (`invoke_without_command=True`) so subcommands (`run`, `view`, `list-*`) remain unchanged for scripts and agents.
- ASCII banner uses the "ANSI Shadow" figlet style (hardcoded in `tui.py`, not generated at runtime — avoids a pyfiglet dependency and keeps the visual stable). Lines are colored with a magenta -> cyan -> blue gradient via Rich. Tagline + live API-key status (● set / ○ missing) render under the banner so the user sees their provider setup at a glance.
- `questionary` added as a dependency for interactive prompts (arrow-key select, multi-select, password input). Chose over raw `typer.prompt` / Rich prompts for arrow-key UX.
- TUI "Run benchmarks" flow: pick a suite YAML OR build a custom run interactively with multi-select over a curated preset of common models (Opus, Haiku, GPT-4o, GPT Image 1, local Llama). Keeps the 80% case menu-driven without needing users to hand-write YAML for their first run.
- TUI "Configure API keys" flow: password-masked input, persisted to `.env` with line-preserving update (only rewrites the specific key line; doesn't clobber other env vars). Live `os.environ` is also updated so the key works immediately in the same session.
- TUI "View past results" flow: queries `Store` for recent runs, presents them as a list, offers open-in-browser or print-in-terminal.
- Noted in README that `npx` is Node-only. The Python equivalents are `uvx benchman` (uv) and `pipx run benchman` — both achieve the zero-install one-command UX the user was describing, once the package is published to PyPI.

## 2026-04-23 — Quality benchmarks + image gen + HTML gallery

### Schema / plumbing
- Introduced a `Prompt` pydantic model (id + prompt + optional `expected`/`check`/`rubric`/`tags`) replacing the `(id, text)` tuple — so quality benchmarks can self-filter by what metadata a prompt carries.
- Added `ModelSpec.benchmarks: list[str] | None` — an optional per-model filter so an image-only model doesn't try to run throughput on text prompts, and vice versa.
- Added `ModelSpec.slug()` for deterministic filesystem paths (`provider__model`, with `/` and `:` normalized).
- `RunManifest.prompts` is now populated — the gallery needs the prompt text to render each section header.
- `BenchmarkResult` gained `score_reasoning: str | None` and `image_paths: list[str]` — avoids stuffing everything into `metadata`.
- `Benchmark.__init__(cfg)` — benchmarks that need suite-level config (judge spec) read it from `self.cfg`. `cfg` is optional so quick scripts and tests can instantiate without a full SuiteConfig.
- `Benchmark.run` gained `output_dir: Path | None` — benchmarks that produce file artifacts (images) write there. Runner computes `<results_dir>/<run_id>` and passes it to every benchmark. Sample_output is no longer truncated to 500 chars — full completions are needed for human eval.

### New benchmarks
- `quality_exact` — contains / exact / regex match against `prompt.expected`. Skips prompts with no `expected`. Score = 1.0 or 0.0.
- `quality_judge` — LLM-as-judge. Generates with the model under test, then asks a judge adapter to score 1-10 with JSON output. Judge defaults to Claude Opus 4.7 when `judge:` isn't in the suite YAML. Parser uses regex + `json.loads` and tolerates non-JSON preamble from the judge.
- `image_gen` — calls `adapter.generate_image()`, writes PNGs to `<output_dir>/images/<model_slug>/<prompt_id>__rep<N>.png`. Latency + n_images + dimensions go into metadata.

### Adapter changes
- `OpenAICompatAdapter.generate_image()` — calls `client.images.generate()`. Handles both `b64_json` and `url` response shapes (different OpenAI image models return different ones; we transparently fetch URLs via `httpx` when needed).

### Gallery
- `reports/html.py` renders a self-contained HTML file at `<results_dir>/<run_id>/gallery.html`. Dark theme, summary table at top, per-prompt sections with a responsive grid of model cards (text preview + images + score + reasoning). Inline CSS — no external deps.
- One card shown per (model, benchmark) per prompt, preferring the first repetition — otherwise the grid balloons with near-identical reruns.

### CLI
- `ai-eval run --open` — auto-opens the gallery in the default browser after a run.
- `ai-eval run --json` — emits a single JSON doc on stdout (run_id, gallery path, full results) for agentic callers. Suppresses the Rich table.
- `ai-eval view <run_id>` and `ai-eval view --latest` — reopens the gallery for a past run; rebuilds the HTML from SQLite if missing.
- `ai-eval list-runs` and `ai-eval list-benchmarks` — round out the introspection surface.
- `Store.load_run()` / `Store.latest_run_id()` — `view` needs to rehydrate a past run from SQLite.

### Notes for the curious
- Agent-first design: every piece the agent needs (metrics, file paths, JSON) is accessible without Rich/HTML. The gallery is the *human* interface; the CLI tables and `--json` are the *machine* interfaces.
- Judge benchmark deliberately re-generates the completion (not reusing the throughput run's output) — keeps benchmarks independent and avoids coupling their execution order. Doubles API cost for quality_judge; worth it for modularity.
- Gallery path layout (`results/<run_id>/{gallery.html,images/...}`) is deliberately isolated per run so you can zip or share a single run without pulling in other runs' artifacts.

## 2026-04-22 — README overhaul

- Rewrote the README around the user workflow: drop in a model, run, compare. Added a flow diagram, an "Adding a model" section with copy-paste YAML for each adapter, queryable SQL examples for human-eval workflows, and an explicit roadmap section (image gen, quality harness, HTML report) so future agents know what's stubbed vs done.

## 2026-04-22 — Readability pass

- Added one-line module docstrings to every file — so the role of each file is visible at a glance without reading its body.
- Collapsed `list[asyncio.Task[list[BenchmarkResult]]]` in `runner.py` to a plain list comprehension — the nested generic was scary for no win; `asyncio.gather` accepts coroutines directly.
- Rewrote SQL INSERTs in `storage.py` to use named parameters — column order and value order can no longer drift out of sync.
- Added a single comment in `throughput.py` noting the tok/s denominator excludes TTFT — otherwise a reader would assume total latency is used.

## 2026-04-22 — Initial scaffold

### Architecture
- Flow: `cli.py` -> `runner.py` -> for each (model, benchmark): `adapters/*` streams a completion -> `benchmarks/*` times it -> `storage.py` saves to SQLite + JSONL.
- Each subsystem has a clear boundary: adapters handle providers, benchmarks define metrics, storage handles persistence, runner handles orchestration. No cross-talk.

### Adapter layer
- Adapter primitive is a single `stream_generate()` method returning text + per-chunk timestamps + final usage — merging streaming and final-usage into one call means TTFT and tok/s come from the same request (no double billing).
- One `OpenAICompatAdapter` class covers OpenAI, vLLM, Ollama, LM Studio, and llama.cpp — they all speak the same chat-completions protocol, only the base URL differs, so duplicating the class would be pure boilerplate.
- The `adapter` field in config picks which env var holds the base URL (`OLLAMA_BASE_URL`, `VLLM_BASE_URL`, etc.) rather than requiring URLs in the YAML — keeps credentials and infra out of the suite definition.
- `stream_options={"include_usage": True}` is passed to OpenAI streams so the final chunk carries real prompt/completion token counts — otherwise we'd only have chunk counts, which aren't tokens.
- There is intentionally no non-streaming `generate()` method — streaming is a superset (you can always collect events into a string), and having one code path prevents provider-specific drift between paths.

### Benchmark layer
- Benchmarks return `list[BenchmarkResult]`, not an async stream — batches are small and the simple interface pays off for new benchmark authors.
- `repetitions` lives in the suite config, not inside the benchmark — noise reduction is a policy decision (how many samples do I want?), not a benchmark detail.
- TTFT is measured from request start (not from socket connect) — this intentionally includes network, queue, and model-load time, which is what a user actually experiences.
- Tok/s denominator is `end - first_token_time` (not total latency) — this isolates generation speed from TTFT, so a slow-to-start but fast-generating model isn't unfairly penalized.

### Storage + schema
- Storage = SQLite (queryable) + JSONL (archival) in parallel — SQLite for ad-hoc analysis, JSONL is append-only and ships to S3 easily.
- The `payload_json` column holds the full pydantic dump of each result, so new benchmark fields never require a DB migration. The top-level columns exist only to make common queries (filter by model, aggregate tok/s) fast.
- Pydantic v2 is used for every type that crosses a boundary (config, DB, CLI output) so JSON <-> object conversion is free. Plain dataclasses are used for in-process values only (GenerationEvent, StreamedGeneration).

### Python-specific choices (noting because you mentioned you're not often in Python)
- `src/ai_eval/` layout (not `ai_eval/` at the repo root) — this prevents a class of "it works when I run from this directory but not that directory" bugs, because the package is never on `sys.path` implicitly.
- `from __future__ import annotations` at the top of every module — makes type hints lazy-evaluated strings. You can then reference types that are defined later in the file without wrapping them in quotes.
- `anthropic>=0.40` and `openai>=1.50` pinned minimums — both SDKs had breaking changes below these versions; bumping further is fine but below is not.
