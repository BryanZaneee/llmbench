"""Command-line entry point. Registered as the `llmbench` script in pyproject.toml.

Calling `llmbench` with no subcommand launches the interactive TUI (tui.py).
Subcommands (`run`, `view`, etc.) remain script- and agent-callable.
"""

from __future__ import annotations

import asyncio
import json
import webbrowser
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from .config import load_suite
from .reports import render_gallery
from .runner import RESULTS_DIR, run_suite
from .schema import BenchmarkResult, RunManifest
from .storage import Store

app = typer.Typer(
    help="llmbench — benchmark any AI model. Run without a subcommand for the interactive TUI.",
    invoke_without_command=True,
)
console = Console()


@app.callback()
def _root(ctx: typer.Context) -> None:
    if ctx.invoked_subcommand is None:
        from .tui import launch

        launch()
        raise typer.Exit()


@app.command("run")
def cmd_run(
    config: Path = typer.Argument(..., exists=True, help="Suite config YAML"),
    open_browser: bool = typer.Option(
        False, "--open", help="Open HTML gallery in browser when finished"
    ),
    as_json: bool = typer.Option(
        False, "--json", help="Emit results as JSON on stdout (for scripts/agents)"
    ),
) -> None:
    """Run a suite defined in a YAML config file."""
    cfg = load_suite(config)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    manifest, results = asyncio.run(run_suite(cfg))

    store = Store(RESULTS_DIR / "results.db")
    store.save_run(manifest, results)
    store.close()

    gallery_path = render_gallery(
        manifest, results, RESULTS_DIR / manifest.run_id / "gallery.html"
    )

    if as_json:
        _print_json(manifest, results, gallery_path)
        return

    _print_results_table(results)
    console.print(f"\n[green]Saved {len(results)} results[/] to {RESULTS_DIR}")
    console.print(f"[cyan]Gallery:[/] {gallery_path}")

    if open_browser:
        webbrowser.open(gallery_path.as_uri())


@app.command("task")
def cmd_task(
    task_id: str = typer.Argument(..., help="Task ID (see `llmbench list-tasks`)"),
    provider: str = typer.Option("anthropic", "--provider", "-p", help="Chat provider"),
    model: str = typer.Option(
        "claude-opus-4-7", "--model", "-m", help="Model name passed to the provider"
    ),
    reps: int = typer.Option(1, "--reps", "-n", min=1, help="Repetitions to run"),
    max_steps: int | None = typer.Option(
        None, "--max-steps", help="Override the task's default step budget"
    ),
    max_tokens: int = typer.Option(4096, "--max-tokens", help="max_tokens passed each turn"),
    temperature: float = typer.Option(0.0, "--temperature", help="Sampling temperature"),
    runs_dir: Path = typer.Option(Path("runs"), "--runs-dir", help="Directory for trace JSON"),
    as_json: bool = typer.Option(False, "--json", help="Emit per-run summary JSON on stdout"),
) -> None:
    """Run an agentic task. Writes one trace JSON per repetition to <runs_dir>/<run_id>.json."""
    from .agent.runner import run_task as run_one
    from .schema import ModelConfig
    from .tasks import get_task

    try:
        task = get_task(task_id)
    except KeyError as e:
        console.print(f"[red]{e}[/]")
        raise typer.Exit(1)

    cfg = ModelConfig(
        provider=provider,
        model=model,
        params={"temperature": temperature, "max_tokens": max_tokens},
    )

    budget_override = None
    if max_steps is not None:
        from .schema import Budget

        budget_override = Budget(max_steps=max_steps)

    summaries: list[dict] = []
    for i in range(reps):
        try:
            trace, path = asyncio.run(
                run_one(
                    task_id,
                    cfg,
                    runs_dir=runs_dir,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    budget_override=budget_override,
                )
            )
        except RuntimeError as exc:
            console.print(f"[red]{exc}[/]")
            raise typer.Exit(1)

        summaries.append(
            {
                "run_id": trace.run_id,
                "trace": str(path),
                "status": trace.status,
                "verdict": trace.verdicts.final_state_check if trace.verdicts else None,
                "steps": len(trace.trace.steps),
                "input_tokens": trace.totals.input_tokens,
                "output_tokens": trace.totals.output_tokens,
                "tool_calls": trace.totals.tool_call_count,
                "wall_time_ms": trace.totals.wall_time_ms,
            }
        )

        if not as_json:
            console.print(
                f"[cyan]rep {i + 1}/{reps}[/] · {task.id}@{task.version} · "
                f"[{('green' if trace.status == 'success' else 'yellow' if trace.status == 'failure' else 'red')}]{trace.status}[/]"
                f" · verdict={trace.verdicts.final_state_check if trace.verdicts else '-'}"
                f" · steps={len(trace.trace.steps)} · tools={trace.totals.tool_call_count}"
            )
            console.print(f"  [dim]{path}[/]")

    if as_json:
        print(json.dumps({"task_id": task_id, "runs": summaries}, indent=2))


@app.command("list-tasks")
def cmd_list_tasks(
    as_json: bool = typer.Option(False, "--json", help="Emit task catalog as JSON on stdout"),
) -> None:
    """Show every registered agentic task."""
    from .tasks import list_tasks

    rows = [
        {"id": cls.id, "version": cls.version, "description": cls.description}
        for cls in list_tasks()
    ]
    if as_json:
        print(json.dumps(rows, indent=2))
        return
    t = Table(title="Tasks")
    t.add_column("ID")
    t.add_column("Ver", style="dim")
    t.add_column("Description")
    for r in rows:
        t.add_row(r["id"], r["version"], r["description"])
    console.print(t)


@app.command("list-models")
def cmd_list_models(
    as_json: bool = typer.Option(False, "--json", help="Emit pricing table as JSON on stdout"),
) -> None:
    """Show every model with a registered price (USD per million tokens)."""
    from .agent.pricing import list_models

    rows = [
        {
            "provider": provider,
            "model": model,
            "input_per_m": price.input_per_million,
            "output_per_m": price.output_per_million,
            "cached_input_per_m": price.cached_input_per_million,
        }
        for provider, model, price in list_models()
    ]
    if as_json:
        print(json.dumps(rows, indent=2))
        return
    t = Table(title="Pricing (USD per 1M tokens)")
    t.add_column("Provider")
    t.add_column("Model")
    t.add_column("Input", justify="right")
    t.add_column("Output", justify="right")
    t.add_column("Cached", justify="right", style="dim")
    for r in rows:
        cached = "" if r["cached_input_per_m"] is None else f"${r['cached_input_per_m']:.2f}"
        t.add_row(
            r["provider"],
            r["model"],
            f"${r['input_per_m']:.2f}",
            f"${r['output_per_m']:.2f}",
            cached,
        )
    console.print(t)


@app.command("view")
def cmd_view(
    run_id: str = typer.Argument(None, help="Run ID (omit with --latest)"),
    latest: bool = typer.Option(False, "--latest", help="View the most recent run"),
) -> None:
    """Open the HTML gallery for a past run."""
    store = Store(RESULTS_DIR / "results.db")
    try:
        if latest:
            run_id = store.latest_run_id()
            if not run_id:
                console.print("[red]No runs found[/]")
                raise typer.Exit(1)
        if not run_id:
            console.print("[red]Provide a run_id or use --latest[/]")
            raise typer.Exit(1)
        manifest, results = store.load_run(run_id)
    finally:
        store.close()

    gallery_path = RESULTS_DIR / manifest.run_id / "gallery.html"
    if not gallery_path.exists():
        render_gallery(manifest, results, gallery_path)
    console.print(f"[cyan]Opening:[/] {gallery_path}")
    webbrowser.open(gallery_path.as_uri())


@app.command("leaderboard")
def cmd_leaderboard(
    source: str = typer.Option(
        "huggingface",
        "--source",
        "-s",
        help="Source to fetch from (huggingface, lmarena, aider, bundled). Use --list-sources to see all.",
    ),
    refresh: bool = typer.Option(False, "--refresh", help="Bypass cache and fetch fresh data"),
    offline: bool = typer.Option(False, "--offline", help="Use cache/bundled data only"),
    top: int = typer.Option(20, "--top", "-n", help="Show top N entries"),
    model_filter: str | None = typer.Option(
        None, "--model", "-m", help="Case-insensitive substring filter on model name"
    ),
    as_json: bool = typer.Option(False, "--json", help="Emit snapshot as JSON on stdout"),
    list_sources: bool = typer.Option(
        False, "--list-sources", help="Show available sources and exit"
    ),
) -> None:
    """Show published benchmark scores from external leaderboards.

    Note: these are published numbers (from HuggingFace / LMArena etc), not
    locally measured. Use `llmbench run` to measure against your own setup.
    """
    from .leaderboards import available_sources, get_source
    from .leaderboards.cache import get_snapshot

    if list_sources:
        for name in available_sources():
            src = get_source(name)
            console.print(f"  [cyan]{name}[/]  {src.description}")
        return

    try:
        src = get_source(source)
    except ValueError as e:
        console.print(f"[red]{e}[/]")
        raise typer.Exit(1)

    try:
        snapshot = get_snapshot(src, refresh=refresh, offline=offline)
    except Exception as exc:  # noqa: BLE001
        console.print(f"[red]Failed to fetch from {source!r}:[/] {exc}")
        raise typer.Exit(1)

    entries = snapshot.entries
    if model_filter:
        q = model_filter.lower()
        entries = [
            e for e in entries
            if q in e.display_name.lower() or q in e.model_id.lower()
        ]
    entries = entries[:top]

    if as_json:
        snap = snapshot.model_copy(update={"entries": entries})
        print(snap.model_dump_json(indent=2))
        return

    _print_leaderboard(snapshot, entries)


def _print_leaderboard(snapshot, entries) -> None:
    if not entries:
        console.print("[yellow]No entries to display.[/]")
        return

    metric_keys: list[str] = []
    seen = set()
    for e in entries:
        for k in e.metrics:
            if k not in seen:
                seen.add(k)
                metric_keys.append(k)

    t = Table(title=f"Leaderboard · {snapshot.source}")
    t.add_column("#", style="dim", width=3)
    t.add_column("Model")
    t.add_column("Org", style="dim")
    for k in metric_keys:
        t.add_column(k.replace("_", " "), justify="right")

    for i, e in enumerate(entries, 1):
        row = [str(i), e.display_name, e.organization]
        for k in metric_keys:
            v = e.metrics.get(k)
            row.append(f"{v:.2f}" if isinstance(v, (int, float)) else "—")
        t.add_row(*row)

    console.print(t)
    console.print(
        f"[dim]source: {snapshot.source_url or snapshot.source}  ·  "
        f"fetched: {snapshot.fetched_at.isoformat(timespec='seconds')}  ·  "
        f"{len(snapshot.entries)} total entries[/]"
    )


def _print_results_table(results: list[BenchmarkResult]) -> None:
    t = Table(title="Benchmark Results")
    for col in ["Model", "Benchmark", "OK", "TTFT ms", "tok/s", "Score", "Out tok", "ms"]:
        t.add_column(col)
    for r in results:
        tp = r.throughput
        t.add_row(
            r.model.display,
            r.benchmark,
            "OK" if r.success else "FAIL",
            f"{tp.ttft_ms:.0f}" if tp and tp.ttft_ms else "-",
            f"{tp.tokens_per_second:.1f}" if tp and tp.tokens_per_second else "-",
            f"{r.score:.1f}" if r.score is not None else "-",
            str(tp.output_tokens) if tp else "-",
            f"{r.duration_ms:.0f}",
        )
    console.print(t)


def _print_json(
    manifest: RunManifest, results: list[BenchmarkResult], gallery_path: Path
) -> None:
    payload = {
        "run_id": manifest.run_id,
        "gallery": str(gallery_path),
        "results": [r.model_dump(mode="json") for r in results],
    }
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    app()
