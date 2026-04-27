"""Per-task agent runner. Builds the provider, drives the loop, persists the trace.

One call to `run_task` runs (task, model) once and writes a single TraceDocument
to the runs directory. Repetitions are handled by the caller looping; we keep
one-shot semantics here so a repetition counter can live in the CLI.
"""

from __future__ import annotations

from pathlib import Path

from ..schema import (
    Budget,
    ModelConfig,
    RunStatus,
    StepList,
    TraceDocument,
    VerdictResult,
    Verdicts,
)
from ..tasks import get_task
from .loop import run_agent
from .provider import ChatProvider
from .providers import build_provider


def save_trace(trace: TraceDocument, runs_dir: Path) -> Path:
    """Persist a TraceDocument to <runs_dir>/<run_id>.json. Returns the path written."""
    runs_dir.mkdir(parents=True, exist_ok=True)
    out = runs_dir / f"{trace.run_id}.json"
    out.write_text(trace.model_dump_json(by_alias=True, indent=2))
    return out


async def run_task(
    task_id: str,
    model_config: ModelConfig,
    *,
    runs_dir: Path = Path("runs"),
    provider: ChatProvider | None = None,
    max_tokens: int = 4096,
    temperature: float = 0.0,
    budget_override: Budget | None = None,
) -> tuple[TraceDocument, Path]:
    """Run one (task, model) repetition end to end. Persists and returns the trace."""

    task = get_task(task_id)
    setup = task.setup()
    budget = budget_override or setup.budget

    owned_provider = provider is None
    chat = provider or build_provider(model_config)

    try:
        outcome = await run_agent(
            chat,
            system=setup.system,
            user_prompt=setup.user_prompt,
            tools=setup.tools,
            budget=budget,
            max_tokens=max_tokens,
            temperature=temperature,
        )
    finally:
        if owned_provider:
            await chat.aclose()

    verdict = task.check()

    # Loop succeeded but the verdict failed: surface that distinction at the top level
    # so a caller scanning trace.status alone can tell apart "ran fine, wrong answer"
    # from "ran out of steps" or "exception".
    final_status = outcome.status
    if outcome.status == RunStatus.SUCCESS and verdict.verdict == VerdictResult.FAIL:
        final_status = RunStatus.FAILURE

    behavior_flags = list(outcome.behavior_flags) + list(verdict.behavior_flags)

    trace = TraceDocument(
        task_id=task.id,
        task_version=task.version,
        target_model=model_config,
        status=final_status,
        totals=outcome.totals,
        verdicts=Verdicts(
            final_state_check=verdict.verdict,
            behavior_flags=behavior_flags,
        ),
        trace=StepList(steps=outcome.steps),
        error=outcome.error or (verdict.detail if verdict.verdict == VerdictResult.FAIL else None),
    )
    return trace, save_trace(trace, runs_dir)
