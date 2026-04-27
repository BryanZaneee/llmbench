# llmbench v1 — PRD

## Overview

llmbench is an open-source agentic benchmark harness. It runs standardized tasks against frontier models, measures efficiency / correctness / behavior / robustness, and renders comparable trace data across providers.

**v1 ships:** a Python engine (built-in agent loop), a Textual TUI, a Next.js web UI, four providers, five task categories.

**v1 non-goals:** BYO-agent mode, OpenTelemetry integration, image generation tasks, custom rubric-based LLM-as-judge. All deferred to v2.

## Users and use cases

- **Engineers picking a model.** "Should I switch from Claude to Gemini for my agent?" Run the suite, get a verdict.
- **Tinkerers / OSS contributors.** Add tasks, add providers, share results.
- **Bryan's portfolio reviewers.** A serious Python codebase with non-trivial concurrency, schema design, and three rendering surfaces.

## Architecture

Three components, one JSON contract. Backend is Python end-to-end (engine, TUI, hosted API). Frontend is TypeScript + Next.js.

```
┌─────────────────────┐       ┌──────────────────┐
│  Python engine      │──────▶│  trace.json      │
│  (agent loop +      │       │  (one per run)   │
│   provider adapters)│       └────────┬─────────┘
└─────────────────────┘                │
                                       │
                ┌──────────────────────┼──────────────────────┐
                ▼                      ▼                      ▼
         ┌─────────────┐        ┌─────────────┐        ┌──────────────┐
         │ Textual TUI │        │ Web UI      │        │ FastAPI svc  │
         │ (local disk)│        │ (IndexedDB  │        │ (Python +    │
         │             │        │  + upload)  │        │  Postgres)   │
         └─────────────┘        └──────┬──────┘        └──────┬───────┘
                                       │                      │
                                       └──────POST/GET────────┘
```

Engine writes a JSON document. TUI reads from local disk. Web UI reads from local file upload (stored in IndexedDB) or from the hosted FastAPI service. Engine has zero awareness of where the artifact ends up.

## Tech stack

- **Engine + TUI** — Python 3.11+. `httpx`, `pydantic`, `typer`, `rich`, `textual`, `anyio`. Dev: `pytest`, `respx`, `mypy`.
- **Web UI** — TypeScript, Next.js 15 (static export), Tailwind, `zod`, `recharts`.
- **Hosted backend** — Python 3.11+, FastAPI, `asyncpg`, Postgres-in-Docker, Caddy as reverse proxy on Hostinger VPS. Reuses Pydantic schemas directly from the engine package.

## Component specs

### Engine

- **CLI surface (intentionally minimal):**
  - `llmbench run <suite> --models <list>` — execute suite, write trace files
  - `llmbench list-models` — show known models + pricing
  - `llmbench list-tasks` — show task catalog
  - That's it. No benchmark dashboards in the CLI. TUI and Web UI own presentation.
- **Agent loop** is provider-agnostic: send messages → receive content + tool calls → execute tools → append results → repeat until stop or budget exceeded.
- **Provider adapters** (see API section below). One adapter per provider, all conforming to a single `ChatProvider` Protocol.
- **Tool runtime** is in-process. Tools are Python callables. Failure injection wraps any tool to fail N times then succeed, or always fail with a specific error.
- **Pricing table** lives in `pricing.yaml`. Updated by hand or PR.
- **Storage backend** is pluggable. Default: write JSON files to `./runs/`. Optional: POST to `LLMBENCH_API_URL` with bearer token.

### TUI (Textual)

- Default surface for local users running benchmarks.
- Screens:
  1. **Suite picker** — list available tasks, select which to run, select models
  2. **Live run** — streaming view of trace as it happens; current step, tool calls, tokens accumulating, cost ticking up
  3. **Results** — completed runs grouped by suite, sortable by model/cost/success
  4. **Trace detail** — full step-by-step view of a single run, scrollable
- Storage is local disk only. TUI never talks to the network except via the engine's provider calls.

### Web UI (Next.js, static export)

- Two ways to load data:
  1. Drop a `trace.json` file into the page → stored in browser IndexedDB → renders the trace explorer
  2. Sign in (API token from hosted backend) → fetches runs from FastAPI → renders trace explorer + comparison views
- Screens:
  1. **Run list** — table of runs, filter by model/task/status
  2. **Trace viewer** — step-by-step trace with token counts and tool call details per step
  3. **Comparison** — pick 2+ runs, see them side-by-side; cost/quality scatter plot for many runs
  4. **Public leaderboard** (only on hosted instance) — aggregated results from runs the user opted to publish
- Static export means hosting cost is near zero (Cloudflare Pages or Vercel free tier).
- TypeScript types for trace data are generated from the engine's Pydantic schema using `datamodel-code-generator`. Single source of truth.

### Hosted backend (deferred to v1.1, defined now)

- **Stack.** FastAPI service, `asyncpg` for Postgres, Postgres running in Docker on the same Hostinger VPS, Caddy as reverse proxy doing TLS. Same VPS layout pattern Bryan already uses for Shuttrr.
- **Why FastAPI over Hono.** The engine's Pydantic models (`TraceDocument`, `Run`, `ModelConfig`) are imported directly into the API service for request validation, response serialization, and OpenAPI doc generation. No schema duplication, no codegen step, no drift risk. Single language across engine + API. Auto-generated `/docs` endpoint for free.
- **Endpoints:**
  - `POST /runs` — upload a trace, body validated against `TraceDocument`
  - `GET /runs/:id` — fetch single run
  - `GET /runs?filter=...` — list runs with filters (model, task, owner, success)
  - `POST /runs/:id/publish` — mark a run as publicly visible on the leaderboard
- **Auth.** API token in `Authorization: Bearer <token>` header. Tokens are tied to user accounts and managed via a small admin surface.
- **Postgres schema.** One `runs` table:
  - `id` UUID primary key
  - `owner_id` UUID, FK to users
  - `model` text, indexed
  - `task_id` text, indexed
  - `status` text, indexed
  - `is_public` boolean, indexed
  - `created_at` timestamptz, indexed
  - `trace` jsonb (the full `TraceDocument`)
- **Deploy.** Single `docker compose up` brings up Postgres + FastAPI service. systemd unit on the host runs `docker compose` and ensures restart on boot. Caddy block routes `api.llmbench.dev` (or whatever subdomain) to the FastAPI port. TLS auto-managed.
- **Engine integration.** Setting `LLMBENCH_API_URL` and `LLMBENCH_API_TOKEN` env vars makes the engine POST every completed run. Default behavior is local-disk-only, hosted is opt-in.

## Trace JSON shape

Authoritative schema lives in `llmbench/schema.py` (Pydantic v2). Same models imported by the FastAPI service for request validation. TypeScript types generated for the web UI. Reference shape:

```json
{
  "run_id": "uuid",
  "created_at": "ISO-8601",
  "suite_hash": "sha256:...",
  "task_id": "file-refactor",
  "task_version": "1.0.0",
  "model_config": {
    "provider": "anthropic | openai | google | moonshot",
    "model": "claude-opus-4-7",
    "params": { "temperature": 0, "max_tokens": 4096 }
  },
  "status": "success | failure | budget_exceeded | error",
  "totals": {
    "input_tokens": 12450,
    "output_tokens": 2100,
    "cached_tokens": 8000,
    "cost_usd": 0.042,
    "wall_time_ms": 18400,
    "time_to_first_token_ms": 620,
    "tool_call_count": 6
  },
  "verdicts": {
    "final_state_check": "pass | fail",
    "behavior_flags": ["looped", "hallucinated_tool"]
  },
  "trace": {
    "steps": [
      {
        "step_id": 0,
        "role": "assistant | tool",
        "content": "string or null",
        "tool_calls": [
          { "name": "read_file", "input": {}, "output": "...", "duration_ms": 12, "error": null }
        ],
        "tokens": { "input": 1200, "output": 80, "cached": 0 },
        "timing_ms": 940
      }
    ]
  }
}
```

## Provider adapters

All four providers reach via `httpx`, no SDKs. Each implements the same Protocol; the engine never branches on provider name above the adapter layer.

### Anthropic (Claude)

- **Endpoint:** `POST https://api.anthropic.com/v1/messages`
- **Auth:** `x-api-key` header, `anthropic-version: 2023-06-01`
- **Tool schema:** `tools: [{ name, description, input_schema }]`
- **Tool call:** content block `{ type: "tool_use", id, name, input }`, signaled by `stop_reason: "tool_use"`
- **Tool result:** user-role content block `{ type: "tool_result", tool_use_id, content }`
- **Usage:** response includes `usage: { input_tokens, output_tokens, cache_creation_input_tokens, cache_read_input_tokens }`
- **Models for v1:** `claude-opus-4-7`, `claude-sonnet-4-7`, `claude-haiku-4-5`

### OpenAI (GPT)

- **Endpoint:** `POST https://api.openai.com/v1/chat/completions` (Chat Completions for v1 — broader compatibility, simpler shape)
- **Auth:** `Authorization: Bearer <key>`
- **Tool schema:** `tools: [{ type: "function", function: { name, description, parameters } }]`
- **Tool call:** assistant message with `tool_calls: [{ id, type: "function", function: { name, arguments } }]` (arguments is a JSON string)
- **Tool result:** message with `role: "tool", tool_call_id, content`
- **Usage:** `usage: { prompt_tokens, completion_tokens, total_tokens }` plus `prompt_tokens_details.cached_tokens` when caching applies
- **Models for v1:** `gpt-5.4`, `gpt-5.4-mini`, `gpt-5.5`

### Google (Gemini)

- **Endpoint:** `POST https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent`
- **Auth:** `x-goog-api-key` header
- **Tool schema:** `tools: [{ function_declarations: [{ name, description, parameters }] }]`
- **Tool call:** content part `{ functionCall: { id, name, args } }` (Gemini 3+ generates a unique `id` per call)
- **Tool result:** content part `{ functionResponse: { id, name, response } }`
- **Thought signatures:** Gemini 3+ returns `thought_signature` in model parts; must be echoed back on next turn for context preservation. Adapter tracks and re-sends automatically.
- **Usage:** `usageMetadata: { promptTokenCount, candidatesTokenCount, totalTokenCount, cachedContentTokenCount }`
- **Models for v1:** `gemini-3-pro`, `gemini-3-flash`, `gemini-2.5-pro`

### Moonshot (Kimi)

- **Endpoint:** `POST https://api.moonshot.ai/v1/chat/completions`
- **Auth:** `Authorization: Bearer <key>`
- **Tool schema:** OpenAI-compatible — `tools: [{ type: "function", function: { name, description, parameters } }]`
- **Tool call / tool result:** identical to OpenAI Chat Completions
- **Usage:** OpenAI-shaped usage object
- **Implementation note:** Kimi adapter inherits from the OpenAI adapter, only overrides `base_url` and pricing. Single class, two endpoints.
- **Models for v1:** `kimi-k2.5`, `kimi-k2.6`, `kimi-k2-thinking`

## Task suite for v1

Five categories, one canonical task per category at launch. Each task ships with a programmatic `final_state_check` and a default `budget`.

1. **File operations** — refactor a function name across a 5-file mock project; success = all references renamed, no broken syntax
2. **API orchestration** — fetch user list from mock API A, transform, post each to mock API B; success = all users posted with correct shape
3. **Multi-step research** — given mocked search results across 4 queries, write a synthesis answering a specific question; success = synthesis contains required facts (substring or rubric-lite check)
4. **Recovery** — first call to `commit_transaction` always fails with a specific error; success = model retries correctly and completes the task
5. **Long-horizon** — 15+ step task: read config, fetch data from 3 mock APIs, transform, write report file with required sections; success = file exists with all sections present

Each task is run **N=10 times per model** by default to capture variance. Configurable via CLI flag.

## Sandboxed tool primitives

Provided by the harness, available to any task:

- `fake_fs` — in-memory filesystem (`read_file`, `write_file`, `list_dir`, `delete_file`)
- `fake_http` — canned route table (`http_get`, `http_post`)
- `fake_sql` — in-memory SQLite (`query`, `insert`, `update`)
- `fake_search` — canned result sets (`search`)
- `fake_shell` — allowlisted commands with canned outputs (`run_command`)
- `failure_injector` — wrapper that makes any tool fail N times then succeed, or always fail

## Milestones

1. **M1 — Engine core (week 1–2).** Pydantic schema, agent loop, Anthropic adapter, fake_fs, file-refactor task, JSON output to disk. End state: `llmbench run file-refactor --models claude-opus-4-7` produces a valid trace.json.
2. **M2 — All providers (week 3).** OpenAI, Gemini, Kimi adapters. Confirm cross-provider parity on file-refactor.
3. **M3 — Full task suite (week 4).** Remaining four task categories, all sandboxed tools. Variance reporting (N runs per task).
4. **M4 — TUI (week 5).** Textual app: suite picker, live run, results, trace detail.
5. **M5 — Web UI core (week 6–7).** Static Next.js app: drop-file viewer, trace explorer, comparison view, cost/quality scatter.
6. **M6 — Polish + launch (week 8).** README, demo recording, blog post draft.
7. **v1.1 (post-launch).** Hosted FastAPI backend on the VPS, public leaderboard. Depends on Hono → FastAPI VPS migration being complete (see migration sub-doc).

## Open questions / risks

- **Gemini thought signatures.** Adapter has to thread these through every turn correctly or multi-turn tool use silently degrades. Needs an integration test specifically for this.
- **Variance budget cost.** N=10 runs × 5 tasks × 4 providers × 3 models per provider = 600 runs per benchmark cycle. At avg $0.05/run that's $30/cycle. Manageable for personal use, worth noting in README so users size expectations.
- **Trace file size.** Long-horizon task could produce 100KB+ traces. Web UI needs to handle this without blocking the main thread. Render virtualized step list.
- **Pricing table drift.** Providers change prices. Bake in a `pricing.last_updated` date and warn in CLI output if it's >90 days old.
- **API rate limits.** v1 runs serially per model to avoid hitting limits. Concurrent runs across different providers are fine. Document this.
- **VPS migration sequencing.** Hosted backend (v1.1) depends on the broader Hono → FastAPI VPS migration. That migration can run in parallel with v1 engine/TUI/Web UI work since they're independent.
