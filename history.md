# History

Running log of design and architecture decisions. One line per entry — the "why" goes here, the "what" is in the code. Newest dates at top.

Agents reading this should skim before touching the code: many choices below are deliberate and look non-obvious from the source alone.

## 2026-04-28 - M4: questionary TUI integration + polish

The M4 plan in `history.md` (M3 entry) called for "Textual TUI screens (live run, results, trace detail)." We prototyped both and picked questionary for v1; the Textual prototype is preserved on the `m4-textual-tui` branch in case we revisit. The remaining task at v1 is integrating the engine surface (M1-M3) into the existing questionary menu and polishing the UX, not introducing a new TUI library.

### Why questionary over Textual

- Questionary is line-oriented, matches the rest of the CLI surface, and renders cleanly in any terminal (including over SSH and dumb terminals). A Textual app pulls in a heavy widget framework, owns the whole screen, and has a different visual idiom than the existing CLI tables. The user prefers the simpler line-by-line questionary style for v1.
- The Textual prototype landed at `9a4aaa5 feat(tui): textual app for browsing traces and configuring runs` and is intact on `m4-textual-tui`. If demand for live-updating screens emerges, we can revive it without re-prototyping.
- The questionary path now exposes every CLI surface a non-developer would use: agentic tasks, benchmarks, leaderboards, past runs, past traces, key configuration. No CLI command is missing from the menu.

### Banner

- "LLM" is yellow, "BENCH" is blue, split at column 27 (the boundary between the M and B blocks). The earlier 6-line magenta-to-blue gradient was visually busy and didn't reinforce the name; a two-color split that maps to the word boundaries reads cleanly.

### Menu structure

- Seven flat items reorganized into three groups via `questionary.Separator`: actions ("Run agentic task", "Run benchmarks"), browse ("View past task traces", "View past benchmark runs", "View published leaderboards"), and config ("Configure API keys", "Quit"). Separators in questionary are non-selectable, so the cursor skips them.
- Renamed "View past results" → "View past benchmark runs" because traces are also "past results"; the new label disambiguates.

### Pricing surfaced in pickers, not as a standalone view

- The agentic-task model picker now embeds per-1M token pricing in each label (`anthropic/claude-opus-4-7  ·  $15/$75 per 1M in/out`). `list-models` from the CLI is *not* added as a standalone TUI menu entry; users browsing models do so as part of choosing one to run, which is when pricing is decision-relevant. A read-only "browse models" view would duplicate the picker and add menu clutter.

### API-key pre-flight

- `_PROVIDER_KEY_BY_ID` (provider id → env var) now backs `_confirm_provider_key()`, which warns and prompts before either flow (`_flow_run`, `_flow_run_task`) launches a run that's guaranteed to fail. Local-only providers (`ollama`, `mock`) are skipped because they have no key requirement. The benchmark flow checks every model's provider in the suite; the task flow checks the single picked provider.

## 2026-04-27 - M3: task suite + remaining sandbox primitives

The four sandbox tools (`fake_http`, `fake_sql`, `fake_search`, `fake_shell`) and the four task scenarios (`api-orchestration`, `multi-step-research`, `recovery`, `long-horizon`) the PRD calls for at v1 launch. With M3 done the engine surface is feature-complete: five tasks across five categories, six sandbox primitives plus a failure injector, and the loop drives all of them.

### Sandbox tools

- `fake_http` is a route table keyed on `(method, path)`. Misses are 404s with descriptive bodies, not exceptions, so the model can probe the surface. Calls (including bodies) are recorded for verdict introspection.
- `fake_sql` wraps stdlib `sqlite3.connect(":memory:")` with `row_factory=Row` so query results come back as dict-like rows. Three operation tools with statement-prefix gating: `sql_query` only accepts SELECT, `sql_insert` only INSERT, `sql_update` accepts UPDATE or DELETE. `sqlite3.Error` is caught and re-raised as `ToolError` so the model sees a clean message instead of a stack trace prefix.
- `fake_search` is exact-string keyed; misses return an empty list. `limit` defaults to 10 to match real search APIs.
- `fake_shell` is allowlisted commands with canned `{stdout, stderr, exit_code}`. NEVER executes anything; the whole point is a sandbox returning canned output. Disallowed commands return exit_code=126 (POSIX "permission denied" semantics) so the model sees a recognizable shell-shaped failure.
- All four follow `fake_fs`'s shape: state class plus per-operation Tool classes plus a `build_fake_*_tools(state) -> dict[str, Tool]` helper. The helpers were initially named `make_fake_*_tools` by parallel agents; renamed to `build_*` to match M1.

### Task suite

- **api-orchestration** seeds 3 users in a `GET /users` route and an audit endpoint at `POST /audit`. The user prompt deliberately requires a field rename (`id` -> `user_id`) so the verdict tests transform behavior, not pass-through. Verdict reads `FakeHttp.calls` and asserts exactly one GET, three POSTs with the right shape, and the right `(user_id, name)` set.
- **multi-step-research** uses a fully fictional company **"Llamatech"** so there is zero ambiguity from the model's training data. Four pre-registered queries return canned results containing specific verifiable facts. The model writes its synthesis to `/research.md` (a fake_fs file the verdict reads) rather than returning text directly, so the verdict stays sandbox-introspection-only and `Task.check()` does not need to be async or take a trace argument. Verdict checks substring matches per fact category. `unregistered_search_query` behavior flag fires if the model issues a query outside the four registered ones.
- **recovery** wraps `SqlInsertTool(state)` in `FailureInjector(fail_times=1)` and overrides the wrapper's `name` and `description` post-construction so the model sees a single tool called `commit_transaction` (per PRD verbiage) without us writing a one-off task-specific tool. After the run, the verdict queries `state._conn` directly (sync sqlite3) since `Task.check()` is sync; checks for exactly one row with `action="login"`, `user_id=42`. `recovered_from_transient_failure` flag fires when the injector counter reached 0 AND a row exists.
- **long-horizon** seeds a `/config.json` listing three source paths plus `output_path` plus `required_sections`. The model has to parse the config, GET each source, transform into markdown with four required headings, and write to the configured output path. Verdict aggregates failures into a single message so a real model run is debuggable in one glance instead of "FAIL". `excessive_http_calls` flag fires past 5 calls (3 expected, 4-5 retry territory, >5 looping). `unexpected_delete` flag is informational. PRD calls this "15+ steps"; budget is 30 steps to leave slack for chain-of-thought turns.

### Task registry

- `tasks/__init__.py` imports each task module so the `@register_task` decorator side-effect populates the registry. One line per task. Resisted the instinct to autodiscover via `pkgutil.iter_modules`; explicit imports keep `list-tasks` stable and surface registration failures at import time instead of silently.

### Behavior flags surfaced by M3

`excessive_http_calls`, `unexpected_delete`, `recovered_from_transient_failure`, `unregistered_search_query` join `hallucinated_tool` from M1. These are informational and do not affect pass/fail; they let the trace viewer (M5) surface coarse model behaviors without re-reading every step.

### Tests

- 28 new tool tests (7 fake_http + 9 fake_sql + 6 fake_search + 6 fake_shell).
- 19 new task tests (4 api-orchestration + 5 multi-step-research + 5 recovery + 5 long-horizon).
- Total: 110 passing (47 new this milestone). Suite runs in ~0.7s.

### Deferred to M4

- Textual TUI screens (live run, results, trace detail).
- README documenting the agent surface alongside the existing benchmark surface.
- A YAML pricing overlay; still no demand.

## 2026-04-27 - M2: providers + cost rollup

Three more chat providers plus per-model pricing land. `llmbench task` now works against OpenAI, Moonshot, and Gemini in addition to Anthropic, and `Totals.cost_usd` is populated after every turn (so the `max_cost_usd` budget gate actually fires instead of being a dead branch).

### Providers

- `OpenAICompatProvider` covers OpenAI and Moonshot from one class. Both expose the same Chat Completions wire format; the differences are base_url and the env var name. Constructor takes `base_url` and `api_key_env` so `build_provider` instantiates one for `provider="openai"` (defaults) and another for `provider="moonshot"` (Moonshot URL + `MOONSHOT_API_KEY`). Same instinct as the existing `OpenAICompatAdapter` in `adapters/`: shared transport, parameterized endpoint.
- `GeminiProvider` is its own class. Google's API has a distinct shape (contents/parts, system_instruction, functionDeclarations, functionCall/functionResponse) so collapsing it into the OpenAI-compatible class would have been forced. Synthesizes per-turn tool-call IDs (`gemini_call_{i}`) since Gemini does not return them. Resolves `tool_call_id` back to a function name by scanning prior assistant turns; the loop's `ChatMessage.role="tool"` carries only the ID, not the name. Acceptable for now; if a future provider needs the name on the tool message itself we can extend the loop.
- Both providers support cached-token accounting (`cached_tokens` / `cachedContentTokenCount`) and map a refused finish reason (`content_filter`, `SAFETY`/`RECITATION`/`BLOCKLIST`) to `StopReason.REFUSED`.
- Both are unit-tested via `httpx.MockTransport` injected through the `client` constructor kwarg. AnthropicProvider already had the same DI seam; we kept the pattern consistent so all three vendors test the wire-format layer the same way.

### Pricing and cost rollup

- `agent/pricing.py` ships a `Price(input_per_million, output_per_million, cached_input_per_million)` NamedTuple keyed on `(provider, model)`. PRD called for a `pricing.yaml`; we deviated to a Python dict for v1 because the data is small (≈12 rows), edits are typed, and adding a model is a one-line change instead of touching a separate config file. A YAML overlay can be layered later without changing the lookup interface.
- `compute_cost(provider, model, totals)` is recomputed from running totals after every turn rather than incrementally, so the loop has no cost accumulator to drift. Unknown `(provider, model)` returns 0.0 silently; the user sees zero cost in the trace and can verify via `llmbench list-models`.
- The loop already had a `max_cost_usd` budget branch that was untriggerable in M1 because cost stayed at 0. With pricing wired in, the gate is now a real gate; a regression test (`test_loop_max_cost_budget_gates`) holds the contract.
- Rates seeded as of 2026-04-27. They drift quarterly; a comment in `pricing.py` calls that out so future runs do not silently ship stale numbers.

### CLI

- `llmbench list-models` shows the pricing table (provider, model, input $/M, output $/M, cached $/M). `--json` for scripting. `list-models` was deferred from M1 explicitly waiting on this table.
- `task` flags unchanged; the new providers are reached via `--provider openai|moonshot|gemini`.

### Tests

- 7 new tests for the OpenAI-compatible provider (happy path, tool-call emission, tool round-trip, cached tokens, missing API key, custom base_url for Moonshot, non-2xx error).
- 8 new tests for Gemini (same coverage plus system-instruction stitching and SAFETY → REFUSED mapping).
- 7 new tests for pricing (lookup hits/misses, no-cache math, cache math, fallback when no cached rate, sorted listing).
- 2 new tests in the loop for cost rollup and the `max_cost_usd` gate.
- Total: 63 passing (24 new + 39 prior). Suite runs in 0.7s.

### Deferred

- M3: remaining four task categories (api-orchestration, multi-step research, recovery, long-horizon) and the rest of the sandboxed primitives (`fake_http`, `fake_sql`, `fake_search`, `fake_shell`).
- YAML pricing overlay for users who want to ship custom rates without editing source. Trivial when the demand shows up.

## 2026-04-26 - Agentic engine v1 (M1: engine core)

Begins the PRD-described agentic surface alongside the existing single-completion benchmarks. Goal: people can test their own agents or run the bundled task suite. M1 is the engine core; later milestones add the remaining providers and tasks.

### Module layout

- New top-level packages: `src/llmbench/agent/` (loop, providers, runner), `src/llmbench/tools/` (sandboxed primitives + failure injector), `src/llmbench/tasks/` (task contract + registry + first task). The existing `adapters/` and `benchmarks/` packages stay put: agentic and single-completion are different mental models and conflating them would force every benchmark to absorb tool-use semantics it does not need. Runs land in `./runs/<run_id>.json` per the PRD, distinct from `./results/` used by benchmarks.

### Schema

- Added `TraceDocument`, `Step`, `StepList`, `StepRole`, `StepTokens`, `ToolCallTrace`, `ModelConfig`, `Totals`, `Verdicts`, `Budget`, `RunStatus`, `VerdictResult` to `schema.py`. The trace shape follows the PRD verbatim except for one Python-specific concession: pydantic v2 reserves the attribute name `model_config` for class config, so the Python field is `target_model` aliased to JSON key `model_config` via `Field(alias="model_config")` and `populate_by_name=True`. `model_dump_json(by_alias=True)` produces the canonical PRD shape.
- Trace `status` and `verdicts.final_state_check` are deliberately separate axes. `status` reflects how the loop ended (`success` / `failure` / `budget_exceeded` / `error`); `verdicts.final_state_check` reflects whether the task itself was achieved. The runner promotes `success` to `failure` when the loop completed cleanly but the verdict failed, so a glance at `status` tells you "ran fine, wrong answer" vs "ran out of steps" vs "exception".

### Loop

- Vendor-neutral `ChatProvider` ABC with one abstract method (`chat(messages, tools, ...)`) returning a `ChatResponse` (`content`, `tool_calls`, `usage`, `stop_reason`, `latency_ms`). The agent loop never branches on provider name above this.
- One trace step per assistant turn (role=`assistant`), with the tool_calls list filled in post-execution (`output`, `duration_ms`, `error` populated). Picked the single-step interpretation of the PRD's trace shape because the example tool_call dict carries both `input` and `output`, which only lines up if a step records a complete round-trip. The `tool` StepRole stays in the enum for forward-compat with async-tool extensions.
- Budget gate runs before each turn so a hit produces an explicit `budget_exceeded` status instead of going silent. Five limits supported: `max_steps`, `max_input_tokens`, `max_output_tokens`, `max_wall_time_ms`, `max_cost_usd`. Cost is unimplemented in M1 (Totals.cost_usd stays 0); pricing.yaml + cost rollup land in M2.
- Hallucinated tool calls (model invokes a name we did not surface) record `error="unknown tool: …"` and add `"hallucinated_tool"` to behavior_flags exactly once per run. Real tools that raise `ToolError` record the error string but do not flag.

### Tools

- `Tool` ABC with `name`, `description`, `input_schema` (JSON-schema dict), and async `run(**kwargs)`. Raising `ToolError` reports back to the model; raising anything else also reports but adds a "tool exception" prefix.
- `FakeFs` is a single in-memory dict shared by `read_file`, `write_file`, `list_dir`, `delete_file`. Tasks own the FakeFs and seed it in `setup()`; `check()` inspects the post-run state on the same instance.
- `FailureInjector` wraps an inner Tool and raises ToolError for the first N calls; mirrors the inner tool's `name`/`description`/`input_schema` so the model sees no behavioral wrapper. `AlwaysFailTool` is a standalone permanent-failure tool.

### Providers

- `MockProvider` lives in `src/llmbench/agent/providers/mock.py` (not `tests/`) because it is a useful library surface for downstream users scripting agent behaviors. Receives a list of pre-baked `ChatResponse`s and emits them in order; records every conversation it received.
- `AnthropicProvider` reaches `https://api.anthropic.com/v1/messages` directly via `httpx.AsyncClient` (no SDK), per the PRD. Translates the vendor-neutral message shape: tool calls become `tool_use` blocks, tool returns become a synthetic `user`-role message with `tool_result` blocks. Reads `cache_read_input_tokens` from usage when present so prompt-cache hits surface in totals.
- `build_provider(ModelConfig)` lazy-imports each concrete provider so a unit test using only the mock does not pay the import cost of httpx-backed providers.

### Tasks

- `Task` ABC + `register_task` decorator + module-level `_REGISTRY`. Importing `llmbench.tasks` triggers each task module's import, which triggers its decorator, which populates the registry. Same registry pattern leaderboards already use.
- Task instances are stateful and single-use: `setup()` seeds the sandbox and returns prompts/tools/budget; `check()` reads the post-run state on the same instance. The runner instantiates a fresh Task per repetition.
- `file-refactor` (id, v1.0.0): seeds a 5-file mock Python project (src/ingest.py, src/pipeline.py, src/cli.py, tests/test_pipeline.py, README.md) all referencing `process_data`. Verdict requires no remaining occurrences of `process_data`, every originally-referenced file now contains `transform_data`, and every Python file still parses via `ast.parse`. Default budget is `max_steps=30`.

### CLI

- `llmbench task <task_id>` and `llmbench list-tasks` added alongside existing `run` / `view` / `leaderboard`. Considered making `run` polymorphic (auto-detect task ID vs. YAML suite path) per the PRD's exact CLI surface, but kept the surfaces separate to avoid disturbing the shipped benchmark `run` path. Renaming and merging is a follow-up. `task` flags: `--provider`, `--model`, `--reps`, `--max-steps`, `--max-tokens`, `--temperature`, `--runs-dir`, `--json`. Default provider/model is `anthropic` / `claude-opus-4-7` so a user with `ANTHROPIC_API_KEY` set can run `llmbench task file-refactor` with no other config.
- `list-models` from the PRD is deferred until pricing.yaml lands in M2.

### Tests

- 17 new tests under `tests/test_agent_*.py` and `tests/test_task_file_refactor.py`. Coverage: loop terminates on end_turn; loop executes a tool then finishes; hallucinated tools flag once; budget gate produces `budget_exceeded`; provider exception produces `error`; FakeFs read/write/list/delete + missing-path errors; FailureInjector fails N then succeeds and mirrors the inner surface; AlwaysFailTool always raises; file-refactor verdict fails on untouched state; file-refactor verdict passes when a scripted MockProvider performs the rename via tool calls; full runner pipeline writes a trace.json with the canonical PRD shape (`model_config` alias intact); runner promotes loop-success-with-failed-verdict to `status="failure"`. All 39 tests pass (22 prior + 17 new).

### Deferred to later milestones

- M2: OpenAI / Gemini / Moonshot providers; pricing.yaml + cost rollup; `list-models`.
- M3: remaining four task categories (api-orchestration, multi-step research, recovery, long-horizon) and the rest of the sandboxed primitives (`fake_http`, `fake_sql`, `fake_search`, `fake_shell`).
- M4-M6: Textual TUI screens for tasks; web trace viewer; hosted FastAPI backend.

## 2026-04-25 — Bloat sweep: drop unused surface area

- Removed pydantic fields with zero readers: `Capability.EMBEDDING`, `Prompt.tags`, `RunManifest.harness_versions`, `RunManifest.notes`. Declared, never read.
- Dropped `pillow` dep (unused; image gen uses URL/b64 from the OpenAI-compat adapter directly). Moved `pyarrow` from required to `[project.optional-dependencies]` under key `lmarena`; only the LMArena source imports it, and it imports lazily so unrelated installs no longer pull ~80MB. Daily refresh workflow now installs with `.[lmarena]`.
- Removed undocumented `list-runs`, `list-adapters`, `list-benchmarks` CLI commands. They weren't in the README and `list-runs` was reaching into `Store._conn` (private). If reintroduced, document them.
- Deduped the results-table renderer between `cli.py` and `tui.py`; one definition lives in `cli.py` (with the richer `Out tok` column) and `tui.py` imports it.
- Killed the half-wired `SuiteConfig.results_dir` knob — TUI hardcoded `Path("results")` everywhere, so the YAML field never took effect. Replaced with a module-level `RESULTS_DIR = Path("results")` in `runner.py` shared by CLI + TUI. Also removed the `--out` option from `llmbench run` / `view` — same reasoning, runner.py owns the path.
- GH refresh workflow no longer commits the four per-source JSONs to `web/data/`; only `web/data/all.json` (the file `web/main.js` actually loads) is committed. The per-source files were pure nightly diff noise. Snapshots are now written to `$RUNNER_TEMP/snapshots/` and merged from there.
- Dropped the unreachable `"1970-01-01T00:00:00+00:00"` fallback in `BundledSource` — `LeaderboardSnapshot.fetched_at` already has a `default_factory`, so the fallback never fired.
- Dropped `write_jsonl()` and the parallel `<run_id>.jsonl` archive. The previous `history.md` line called it "append-only, ships to S3 easily" but the code opened with `"w"` mode and rewrote the whole file at end-of-run. SQLite's `payload_json` column already holds the same per-result pydantic dump; query it with `json_extract` instead.

## 2026-04-25 — VPS deploy + bare-path redirect

- Confirmed the deploy chain works end-to-end: GitHub push → `webhook.service` (port 9000, exposed by Caddy at `bryanzane.com/hooks/*`) → `/opt/deploy/deploy.sh` runs `git fetch && git reset --hard origin/main` for the repo whose name matches `REPO_MAP`. `llmbench` → `/var/www/llmbench/` was already mapped by an earlier hand. No new infrastructure needed.
- Caddy block for `/llmbench/*` already existed in the `bryanzane.com` site block (`handle_path /llmbench/* { root * /var/www/llmbench/web; file_server }`).
- `bryanzane.com/llmbench/` (with trailing slash) worked from day one. **`bryanzane.com/llmbench` (without slash) returned 404** because `handle_path /llmbench/*` doesn't match the bare prefix. Fixed by adding `redir /llmbench /llmbench/ permanent` directly above the handle_path block. `caddy validate` complained about the Cloudflare DNS module (env file isn't read in validate context), but the running service reload was clean.
- Portfolio link in `bryanzane_v3` now points at `/llmbench/` directly to skip the redirect roundtrip. Preserves a snappier first paint when entering from the project card.
- VPS layout (paths, deploy script, webhook secret location) captured in `CLAUDE.md` so future agents don't have to re-derive it.

## 2026-04-25 — Web filter overhaul + Aider source

- Web hero now uses the ASCII banner *as* the H1 (wrapped in `<h1 class="lb-banner-h1">`) and drops the separate "llmbench." serif title. The banner already says the name; a second, larger restatement of it underneath was visual duplication. Banner upsized one step to carry the title weight on its own.
- Replaced the explorer's checkbox source filter + sortable column headers with a unified chip-based control surface: source chips, provider chips (Anthropic / OpenAI / Google / Meta / Mistral / DeepSeek / Qwen / xAI / Other), benchmark/metric chips, and sort chips. Reason: the user's audience here is non-developers browsing on bryanzane.com — discoverable click targets beat hidden affordances like "click a column header to sort."
- Provider chips use a small allowlist of fragment matches (`anthropic`, `openai`, `meta-llama`, …) to map raw `organization` strings into clean labels. Anything that doesn't match falls under "Other". Auto-generating the allowlist from data was tempting but produced noisy chips like random HF usernames; the curated list keeps the chip row scannable.
- Metric chip selection is single-select and drives the active "Score" column header — picking `MMLU-PRO` filters to rows that publish that key and labels the column "MMLU-PRO". `Auto` (default) reverts each row to its source's primary metric (HF→avg, LMArena→elo, Aider→polyglot %). This is what makes "filter by benchmark" usable without forcing a source selection first.
- Pagination: table caps at 25 rows with a "Load 25 more" button. Filter / sort / metric changes reset the limit. Reason: the merged dataset is ~600 rows; rendering all of them on first paint was ~1.5s of layout on mid-tier laptops.
- New source: `aider` (Aider Polyglot multi-language coding benchmark). Pulls the YAML at `raw.githubusercontent.com/Aider-AI/aider/main/aider/website/_data/polyglot_leaderboard.yml` directly — small, stable, no auth, no pagination. Headline metric is `polyglot_pass_rate` (pass_rate_2 in the upstream file, percentage of cases solved within two attempts). `pyyaml` is already a dep so no new runtime weight.
- Aider entries don't carry an explicit organization, so we infer it from a model-name fragment heuristic (`claude` → anthropic, `gpt-` → openai, etc.). Imperfect but covers the major providers. Unknown stays "unknown" rather than guessing wrong.
- Skipped SWE-bench Verified and Humanity's Last Exam this pass, even though they were on the wishlist. SWE-bench publishes results as per-submission directories under `swe-bench/experiments` — fetching the leaderboard means walking many files via the GitHub API, which is rate-limit-prone for a daily cron and doesn't fit the "single HTTP fetch" pattern the other sources use. HLE has no public structured endpoint I'm aware of (the lastexam.ai page is the canonical view; scraping HTML risks ToS issues like Artificial Analysis was). Both stay open; would need either a maintained mirror or willingness to accept a more complex fetcher to land cleanly.
- Daily refresh workflow now also fetches `aider --top 200`. Local seed snapshots regenerated to include 69 Aider entries; merged `all.json` is 576 entries across 4 sources.

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
- Storage = SQLite, with the full pydantic dump kept in a `payload_json` column. Earlier we wrote a parallel JSONL archive but it duplicated the same payload, so it was removed; query the column with `json_extract` if you need raw rows.
- The `payload_json` column holds the full pydantic dump of each result, so new benchmark fields never require a DB migration. The top-level columns exist only to make common queries (filter by model, aggregate tok/s) fast.
- Pydantic v2 is used for every type that crosses a boundary (config, DB, CLI output) so JSON <-> object conversion is free. Plain dataclasses are used for in-process values only (GenerationEvent, StreamedGeneration).

### Python-specific choices (noting because you mentioned you're not often in Python)
- `src/ai_eval/` layout (not `ai_eval/` at the repo root) — this prevents a class of "it works when I run from this directory but not that directory" bugs, because the package is never on `sys.path` implicitly.
- `from __future__ import annotations` at the top of every module — makes type hints lazy-evaluated strings. You can then reference types that are defined later in the file without wrapping them in quotes.
- `anthropic>=0.40` and `openai>=1.50` pinned minimums — both SDKs had breaking changes below these versions; bumping further is fine but below is not.
