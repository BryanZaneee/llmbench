"""Command-line entry point. Registered as the `benchman` script in pyproject.toml.

Calling `benchman` with no subcommand launches the interactive TUI (tui.py).
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
from .runner import run_suite
from .schema import BenchmarkResult, RunManifest
from .storage import Store, write_jsonl

app = typer.Typer(
    help="benchman — benchmark any AI model. Run without a subcommand for the interactive TUI.",
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
    out: Path = typer.Option(Path("results"), help="Output directory"),
    open_browser: bool = typer.Option(
        False, "--open", help="Open HTML gallery in browser when finished"
    ),
    as_json: bool = typer.Option(
        False, "--json", help="Emit results as JSON on stdout (for scripts/agents)"
    ),
) -> None:
    """Run a suite defined in a YAML config file."""
    cfg = load_suite(config)
    out.mkdir(parents=True, exist_ok=True)
    manifest, results = asyncio.run(run_suite(cfg))

    store = Store(out / "results.db")
    store.save_run(manifest, results)
    store.close()
    write_jsonl(results, out / f"{manifest.run_id}.jsonl")

    gallery_path = render_gallery(manifest, results, out / manifest.run_id / "gallery.html")

    if as_json:
        _print_json(manifest, results, gallery_path)
        return

    _print_summary(results)
    console.print(f"\n[green]Saved {len(results)} results[/] to {out}")
    console.print(f"[cyan]Gallery:[/] {gallery_path}")

    if open_browser:
        webbrowser.open(gallery_path.as_uri())


@app.command("view")
def cmd_view(
    run_id: str = typer.Argument(None, help="Run ID (omit with --latest)"),
    out: Path = typer.Option(Path("results"), help="Results directory"),
    latest: bool = typer.Option(False, "--latest", help="View the most recent run"),
) -> None:
    """Open the HTML gallery for a past run."""
    store = Store(out / "results.db")
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

    gallery_path = out / manifest.run_id / "gallery.html"
    if not gallery_path.exists():
        render_gallery(manifest, results, gallery_path)
    console.print(f"[cyan]Opening:[/] {gallery_path}")
    webbrowser.open(gallery_path.as_uri())


@app.command("list-runs")
def cmd_list_runs(
    out: Path = typer.Option(Path("results"), help="Results directory"),
    limit: int = typer.Option(10, help="How many recent runs to show"),
) -> None:
    """List recent runs."""
    store = Store(out / "results.db")
    try:
        rows = store._conn.execute(
            "SELECT run_id, created_at, suite_version FROM runs "
            "ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    finally:
        store.close()
    t = Table(title="Recent runs")
    for col in ["run_id", "created_at", "suite_version"]:
        t.add_column(col)
    for run_id, created, version in rows:
        t.add_row(run_id[:12], created, version)
    console.print(t)


@app.command("list-adapters")
def cmd_list() -> None:
    """Show supported adapters."""
    from .adapters import _REGISTRY

    for name, cls in sorted(_REGISTRY.items()):
        console.print(f"  [cyan]{name}[/] -> {cls.__name__}")


@app.command("list-benchmarks")
def cmd_list_benchmarks() -> None:
    """Show registered benchmarks."""
    from .benchmarks import _REGISTRY

    for name, cls in sorted(_REGISTRY.items()):
        console.print(f"  [cyan]{name}[/] -> {cls.__name__}")


@app.command("leaderboard")
def cmd_leaderboard(
    source: str = typer.Option(
        "huggingface",
        "--source",
        "-s",
        help="Source to fetch from (huggingface, lmarena, bundled). Use --list-sources to see all.",
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
    locally measured. Use `benchman run` to measure against your own setup.
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


def _print_summary(results: list[BenchmarkResult]) -> None:
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
