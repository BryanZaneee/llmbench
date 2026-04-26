"""Interactive terminal menu, shown when `llmbench` is invoked with no subcommand.

Wraps the same operations the scriptable CLI exposes (run, view, list) but with a
guided flow: ASCII banner, menu, model/benchmark multi-selects, .env key setter.
"""

from __future__ import annotations

import asyncio
import os
import webbrowser
from pathlib import Path

import questionary
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from .config import SamplingParams, SuiteConfig
from .reports import render_gallery
from .runner import RESULTS_DIR, run_suite
from .schema import ModelSpec
from .storage import Store

console = Console()


BANNER = r"""
██╗     ██╗     ███╗   ███╗██████╗ ███████╗███╗   ██╗ ██████╗██╗  ██╗
██║     ██║     ████╗ ████║██╔══██╗██╔════╝████╗  ██║██╔════╝██║  ██║
██║     ██║     ██╔████╔██║██████╔╝█████╗  ██╔██╗ ██║██║     ███████║
██║     ██║     ██║╚██╔╝██║██╔══██╗██╔══╝  ██║╚██╗██║██║     ██╔══██║
███████╗███████╗██║ ╚═╝ ██║██████╔╝███████╗██║ ╚████║╚██████╗██║  ██║
╚══════╝╚══════╝╚═╝     ╚═╝╚═════╝ ╚══════╝╚═╝  ╚═══╝ ╚═════╝╚═╝  ╚═╝
"""

TAGLINE = "benchmark any AI model · any provider · one command"

# Gradient across the banner lines for visual polish.
_GRADIENT = ["bright_magenta", "magenta", "bright_cyan", "cyan", "bright_blue", "blue"]


# Curated preset models for the "Build a custom run" flow.
PRESET_MODELS: list[ModelSpec] = [
    ModelSpec(provider="anthropic", adapter="anthropic", model="claude-opus-4-7",
              label="Claude Opus 4.7"),
    ModelSpec(provider="anthropic", adapter="anthropic", model="claude-sonnet-4-6",
              label="Claude Sonnet 4.6"),
    ModelSpec(provider="anthropic", adapter="anthropic", model="claude-haiku-4-5-20251001",
              label="Claude Haiku 4.5"),
    ModelSpec(provider="openai", adapter="openai", model="gpt-4o", label="GPT-4o"),
    ModelSpec(provider="openai", adapter="openai", model="gpt-4o-mini", label="GPT-4o mini"),
    ModelSpec(provider="openai", adapter="openai", model="gpt-image-1",
              label="GPT Image 1", benchmarks=["image_gen"]),
    ModelSpec(provider="ollama", adapter="ollama", model="llama3.2",
              label="Llama 3.2 (local Ollama)"),
]

BENCHMARK_CHOICES = ["throughput", "quality_exact", "quality_judge", "image_gen"]

PROVIDER_KEYS = {
    "Anthropic (Claude)": "ANTHROPIC_API_KEY",
    "OpenAI": "OPENAI_API_KEY",
}

ENV_PATH = Path(".env")


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

def launch() -> None:
    _render_banner()
    while True:
        choice = questionary.select(
            "What would you like to do?",
            choices=[
                "Run benchmarks",
                "View published leaderboards",
                "Configure API keys",
                "View past results",
                "Quit",
            ],
        ).ask()

        if choice is None or choice == "Quit":
            console.print("[dim]bye[/]")
            return
        if choice == "Run benchmarks":
            _flow_run()
        elif choice == "View published leaderboards":
            _flow_leaderboard()
        elif choice == "Configure API keys":
            _flow_configure_keys()
        elif choice == "View past results":
            _flow_view_past()


# ─────────────────────────────────────────────────────────────────────────────
# Banner
# ─────────────────────────────────────────────────────────────────────────────

def _render_banner() -> None:
    lines = [line for line in BANNER.splitlines() if line.strip()]
    text = Text()
    for line, color in zip(lines, _GRADIENT):
        text.append(line + "\n", style=f"bold {color}")
    console.print(text)
    console.print(f"  [dim]{TAGLINE}[/]")
    console.print(f"  {_keys_status_line()}\n")


def _keys_status_line() -> str:
    parts = []
    for label, env_name in PROVIDER_KEYS.items():
        if os.environ.get(env_name):
            parts.append(f"[green]●[/] {label}")
        else:
            parts.append(f"[red]○[/] {label}")
    return "API keys: " + "   ".join(parts)


# ─────────────────────────────────────────────────────────────────────────────
# Run flow
# ─────────────────────────────────────────────────────────────────────────────

def _flow_run() -> None:
    style = questionary.select(
        "How do you want to run?",
        choices=[
            "Build a custom run interactively",
            "Load a suite YAML file",
            "Back",
        ],
    ).ask()

    if style is None or style == "Back":
        return
    if style == "Load a suite YAML file":
        path = questionary.path("Path to suite YAML:", default="suite.example.yaml").ask()
        if not path:
            return
        from .config import load_suite
        cfg = load_suite(path)
    else:
        cfg = _build_custom_suite()
        if cfg is None:
            return

    open_when_done = questionary.confirm(
        "Open HTML gallery in browser when finished?", default=True
    ).ask()
    _execute_run(cfg, open_browser=bool(open_when_done))


def _build_custom_suite() -> SuiteConfig | None:
    model_labels = [m.display for m in PRESET_MODELS]
    picked = questionary.checkbox(
        "Select models (space to toggle, enter to confirm):",
        choices=model_labels,
    ).ask()
    if not picked:
        console.print("[yellow]No models selected[/]")
        return None
    selected_models = [m for m in PRESET_MODELS if m.display in picked]

    benchmarks = questionary.checkbox(
        "Select benchmarks:",
        choices=BENCHMARK_CHOICES,
        default=None,
    ).ask()
    if not benchmarks:
        console.print("[yellow]No benchmarks selected[/]")
        return None

    reps_raw = questionary.text("Repetitions per prompt:", default="3").ask()
    try:
        reps = max(1, int(reps_raw or "3"))
    except ValueError:
        reps = 3

    prompts_default = "prompts/default.yaml"
    prompts_file = questionary.text(
        "Prompts file (blank for built-in defaults):", default=prompts_default
    ).ask()
    prompts_file = prompts_file.strip() or None
    if prompts_file and not Path(prompts_file).exists():
        console.print(f"[yellow]Prompts file {prompts_file!r} not found; using built-in[/]")
        prompts_file = None

    return SuiteConfig(
        models=selected_models,
        benchmarks=benchmarks,
        prompts_file=prompts_file,
        repetitions=reps,
        concurrency=min(2, len(selected_models)),
        sampling=SamplingParams(),
    )


def _execute_run(cfg: SuiteConfig, *, open_browser: bool) -> None:
    out = RESULTS_DIR
    out.mkdir(parents=True, exist_ok=True)

    with console.status("[cyan]Running benchmarks..."):
        manifest, results = asyncio.run(run_suite(cfg))

    store = Store(out / "results.db")
    store.save_run(manifest, results)
    store.close()
    gallery = render_gallery(manifest, results, out / manifest.run_id / "gallery.html")

    from .cli import _print_results_table
    _print_results_table(results)
    console.print(f"\n[green]Saved {len(results)} results[/] to {out}")
    console.print(f"[cyan]Gallery:[/] {gallery}")
    if open_browser:
        webbrowser.open(gallery.as_uri())


# ─────────────────────────────────────────────────────────────────────────────
# Leaderboard flow
# ─────────────────────────────────────────────────────────────────────────────

def _flow_leaderboard() -> None:
    from .leaderboards import available_sources, get_source
    from .leaderboards.cache import get_snapshot

    source_descriptions = []
    for name in available_sources():
        src = get_source(name)
        source_descriptions.append(f"{name}  —  {src.description}")

    pick = questionary.select(
        "Pick a source:",
        choices=source_descriptions + ["Back"],
    ).ask()
    if pick is None or pick == "Back":
        return

    source_name = pick.split("  ")[0]
    refresh = questionary.confirm(
        "Force refresh (bypass cache)?", default=False
    ).ask()

    src = get_source(source_name)
    try:
        with console.status(f"[cyan]Fetching from {source_name}..."):
            snapshot = get_snapshot(src, refresh=bool(refresh))
    except Exception as exc:  # noqa: BLE001
        console.print(f"[red]Failed:[/] {exc}")
        return

    name_filter = questionary.text(
        "Filter by model name (blank for all):", default=""
    ).ask()

    n_raw = questionary.text("How many rows to display?", default="20").ask()
    try:
        top_n = max(1, int(n_raw or "20"))
    except ValueError:
        top_n = 20

    entries = snapshot.entries
    if name_filter and name_filter.strip():
        q = name_filter.strip().lower()
        entries = [
            e for e in entries
            if q in e.display_name.lower() or q in e.model_id.lower()
        ]
        if not entries:
            console.print(f"[yellow]No models matched {name_filter!r}[/]")
            return

    from .cli import _print_leaderboard
    _print_leaderboard(snapshot, entries[:top_n])


# ─────────────────────────────────────────────────────────────────────────────
# API-key configuration flow
# ─────────────────────────────────────────────────────────────────────────────

def _flow_configure_keys() -> None:
    while True:
        labels = [
            f"{label}  " + ("[set]" if os.environ.get(env) else "[not set]")
            for label, env in PROVIDER_KEYS.items()
        ]
        pick = questionary.select(
            "Which key do you want to set?",
            choices=labels + ["Back"],
        ).ask()
        if pick is None or pick == "Back":
            return
        label = pick.split("  ")[0]
        env_name = PROVIDER_KEYS[label]
        value = questionary.password(f"{env_name}:").ask()
        if value is None:
            continue
        value = value.strip()
        if not value:
            console.print("[yellow]No value entered; skipping[/]")
            continue
        _write_env_var(env_name, value)
        os.environ[env_name] = value
        console.print(f"[green]Saved[/] {env_name} to {ENV_PATH}")


def _write_env_var(key: str, value: str) -> None:
    existing: list[str] = []
    if ENV_PATH.exists():
        existing = ENV_PATH.read_text().splitlines()
    found = False
    new_lines: list[str] = []
    for line in existing:
        if line.startswith(f"{key}="):
            new_lines.append(f"{key}={value}")
            found = True
        else:
            new_lines.append(line)
    if not found:
        new_lines.append(f"{key}={value}")
    ENV_PATH.write_text("\n".join(new_lines) + "\n")


# ─────────────────────────────────────────────────────────────────────────────
# View past results flow
# ─────────────────────────────────────────────────────────────────────────────

def _flow_view_past() -> None:
    results_dir = RESULTS_DIR
    if not (results_dir / "results.db").exists():
        console.print("[yellow]No past runs found (results/results.db doesn't exist yet)[/]")
        return

    store = Store(results_dir / "results.db")
    try:
        rows = store._conn.execute(
            "SELECT run_id, created_at, suite_version FROM runs "
            "ORDER BY created_at DESC LIMIT 20"
        ).fetchall()
    finally:
        store.close()

    if not rows:
        console.print("[yellow]No runs recorded[/]")
        return

    labels = [f"{rid[:12]}  {created}  (v{version})" for rid, created, version in rows]
    pick = questionary.select(
        "Pick a run to view:",
        choices=labels + ["Back"],
    ).ask()
    if pick is None or pick == "Back":
        return

    run_id = pick.split()[0]
    store = Store(results_dir / "results.db")
    try:
        # load_run needs the full run_id; look it up by prefix
        full_id = next(r[0] for r in rows if r[0].startswith(run_id))
        manifest, results = store.load_run(full_id)
    finally:
        store.close()

    action = questionary.select(
        "What would you like to do?",
        choices=[
            "Open the gallery in browser",
            "Print summary in terminal",
            "Back",
        ],
    ).ask()

    if action == "Open the gallery in browser":
        gallery = results_dir / manifest.run_id / "gallery.html"
        if not gallery.exists():
            render_gallery(manifest, results, gallery)
        webbrowser.open(gallery.as_uri())
    elif action == "Print summary in terminal":
        from .cli import _print_results_table
        _print_results_table(results)
        console.print(
            Panel(
                f"run_id: {manifest.run_id}\n"
                f"created: {manifest.created_at}\n"
                f"models: {', '.join(m.display for m in manifest.models)}\n"
                f"benchmarks: {', '.join(manifest.benchmarks)}",
                title="Run details",
            )
        )
