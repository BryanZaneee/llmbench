# AGENTS.md

Project-level instructions for AI agents working on **llmbench**. Kept local (gitignored), not part of the public repo.

---

## What this is

A CLI-first Python harness for benchmarking LLMs across providers. Lives at [github.com/BryanZaneee/llmbench](https://github.com/BryanZaneee/llmbench). MIT-licensed. Open source.

Two surfaces:
- **CLI** (`llmbench run ...`, `llmbench leaderboard ...`) — scriptable, agent-friendly, `--json` everywhere.
- **TUI** (`llmbench` with no args) — interactive menu with ASCII banner, for humans.

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
- **No `Co-Authored-By: Codex` lines** (user preference).
- Commit message body explains *why*, not just *what* — the diff shows the what.

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
  schema.py            pydantic shapes crossing boundaries
  config.py            YAML / .env loading
  runner.py            async orchestrator
  storage.py           SQLite + JSONL
  cli.py               typer commands
  tui.py               interactive menu
  adapters/            per-provider (Adapter ABC in base.py)
  benchmarks/          per-metric (Benchmark ABC in base.py)
  leaderboards/        published-score sources + cache
  reports/             HTML gallery renderer
  data/                bundled static snapshots
tests/                 one test file per module under test
```
