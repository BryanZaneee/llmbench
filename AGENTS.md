# AGENTS.md

Project-level instructions for AI agents working on **llmbench**. Tracked in the public repo so external contributors and tooling agents pick up the same conventions.

---

## What this is

A CLI-first Python harness for benchmarking LLMs and running sandboxed agentic tasks. Lives at [github.com/BryanZaneee/llmbench](https://github.com/BryanZaneee/llmbench). MIT-licensed. Open source.

Two surfaces, two evaluation modes:
- **CLI** (`llmbench run`, `llmbench task`, `llmbench leaderboard`, `llmbench list-tasks`, `llmbench list-models`, `llmbench view`): scriptable, agent-friendly, `--json` everywhere.
- **TUI** (`llmbench` with no args): interactive questionary menu with ASCII banner, grouped Run / Browse / Config sections, key pre-flight, inline pricing in the model picker.
- **Benchmark mode** (`run`): measures throughput, quality (exact / judge), and image generation against a YAML-defined suite of (model × benchmark) pairs.
- **Agent mode** (`task`): runs a registered `Task` through the agent loop with sandboxed tools (`fake_fs` / `fake_http` / `fake_sql` / `fake_search` / `fake_shell` / `failure_injector`), writes a full `TraceDocument` to `runs/<run_id>.json`.

---

## Before you change anything architectural

**Read `history.md` first.** It's the project's running architecture log — one entry per meaningful decision, with the *why*. Scanning it before a non-trivial change prevents re-litigating settled questions.

Typical signals that a change is "architectural" and warrants a history entry:
- Adding / removing a provider adapter, benchmark, or leaderboard source.
- Changing a public contract (`Adapter`, `Benchmark`, `LeaderboardSource`, the schemas in `schema.py`).
- Adding a runtime dependency.
- Picking between two viable approaches for a non-obvious reason.

Typical signals that it's *not* worth a history entry:
- Routine bug fixes with obvious causes.
- Test-only additions covering existing behavior.
- Typos / formatting.

---

## After you change something architectural

Append to `history.md` under the latest date (or a new dated section at the top). One bullet per decision. Lead with the rule/fact, follow with the *why* when it's non-obvious.

Keep it terse. A single line saying "chose X over Y because Z" is more useful than a paragraph.

---

## Code style

- **Single-purpose modules.** Each file has a module-level docstring describing its role.
- **Type hints everywhere.** `from __future__ import annotations` at the top of every file.
- **Comment the *why*, not the *what*.** Self-explanatory code is preferred over explanatory comments.
- **Minimal dependencies.** Justify any new dep in history.md.
- **Don't invent abstractions.** Match the shape of the existing code — new benchmarks/adapters/sources should look like siblings of the existing ones.

---

## Testing

Run before every commit:

```bash
.venv/bin/pytest -q
```

All tests must pass. Tests for new benchmarks/adapters use the same mock patterns you'll see in `tests/test_throughput.py` and `tests/test_leaderboard.py`.

---

## Commits

- **Small, single-concern commits.** One feature or fix per commit.
- **No AI coauthor trailers** (`Co-Authored-By: Claude`, `Co-Authored-By: Codex`, etc.); user preference.
- **Labeled subjects** in the 50/72 style: `feat:`, `fix:`, `chore:`, `docs:`, `refactor:`, `test:`. Optional scope: `feat(tui): ...`.
- Commit message body explains *why*, not just *what*; the diff shows the what.
- No em dashes in commits, code comments, or docs (user preference). Use commas, semicolons, or periods.

---

## Deploy / VPS

The web surface (`web/`) is served by Caddy on the user's VPS as `bryanzane.com/llmbench/`. Same VPS hosts the portfolio at `bryanzane.com`.

- **VPS:** `ssh root@100.88.216.70`
- **Repo on disk:** `/var/www/llmbench/` (cloned from `BryanZaneee/llmbench`, on `main`).
- **Caddy config:** `/etc/caddy/Caddyfile`. The bryanzane.com site block already includes `redir /llmbench /llmbench/ permanent` followed by `handle_path /llmbench/* { root * /var/www/llmbench/web; file_server }`. The redirect is needed because `handle_path /llmbench/*` doesn't match the bare `/llmbench` (no trailing slash).
- **Auto-deploy:** GitHub webhook → `webhook.service` (systemd, port 9000) → `/opt/deploy/deploy.sh`. The deploy script's `REPO_MAP` already maps `llmbench` → `/var/www/llmbench`. Webhook is exposed via Caddy's `handle /hooks/*` route on bryanzane.com.
- **Daily data refresh:** the GitHub Action in `.github/workflows/refresh-leaderboards.yml` re-fetches all leaderboard sources, commits the JSON back to `main`, and the webhook pulls. The VPS does **not** run Python.
- **Editing the Caddyfile:** keep the existing backup convention (`Caddyfile.bak.YYYYMMDD-HHMMSS`), `caddy validate` (note: validate runs without the env file so the Cloudflare DNS module errors — the running service is fine), `systemctl reload caddy`.

---

## Quick directory map

```
src/llmbench/
  schema.py            pydantic shapes crossing boundaries (incl. TraceDocument)
  config.py            YAML / .env loading
  runner.py            async benchmark orchestrator
  storage.py           SQLite (results/results.db); payload_json column has full pydantic dumps
  cli.py               typer commands; `llmbench` with no args invokes tui.launch()
  tui.py               questionary menu (banner + grouped Run/Browse/Config sections)
  adapters/            per-provider streaming adapter for benchmarks (Adapter ABC in base.py)
  benchmarks/          per-metric (Benchmark ABC in base.py): throughput, quality_exact, quality_judge, image_gen
  agent/               vendor-neutral agent loop + ChatProvider implementations + pricing/cost rollup
    loop.py            single-turn step executor with budget gating + hallucinated-tool detection
    runner.py          run_task entry point; writes runs/<run_id>.json
    pricing.py         (provider, model) -> Price lookup; compute_cost from Totals
    providers/         anthropic, openai (covers moonshot via base_url), gemini, mock
  tasks/               agentic scenarios (Task ABC in base.py); registry populated on import
                       file_refactor, api_orchestration, multi_step_research, recovery, long_horizon
  tools/               sandboxed primitives (Tool ABC in base.py): fake_fs, fake_http, fake_sql,
                       fake_search, fake_shell, failure_injector
  leaderboards/        published-score sources + 24h-TTL cache (huggingface, lmarena, aider, bundled)
  reports/             HTML gallery renderer (results/<run_id>/gallery.html)
  data/                bundled static snapshots (offline leaderboard fallback)
tests/                 one test file per module under test (110 passing as of M4)
runs/                  trace JSONs from `llmbench task` (gitignored)
results/               benchmark outputs from `llmbench run` (gitignored)
web/                   static page served at bryanzane.com/llmbench (data refreshed daily by GH Action)
```
