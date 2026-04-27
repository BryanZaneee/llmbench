"""Agent loop. Provider-agnostic, drives turns until stop_reason or budget hit.

Trace shape: one Step per assistant turn (role="assistant"). The model's content
plus all tool_calls it requested on that turn are recorded together; each
tool_call is filled in post-execution with `output`, `duration_ms`, and `error`.
The "tool" StepRole is reserved for future asynchronous-tool extensions.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field

from ..schema import (
    Budget,
    RunStatus,
    Step,
    StepRole,
    StepTokens,
    ToolCallTrace,
    Totals,
)
from ..tools.base import Tool, ToolError
from .pricing import compute_cost
from .provider import ChatMessage, ChatProvider, StopReason, ToolDefinition


@dataclass
class LoopOutcome:
    status: RunStatus
    steps: list[Step]
    totals: Totals
    error: str | None = None
    behavior_flags: list[str] = field(default_factory=list)


def _budget_exceeded(totals: Totals, budget: Budget, step_count: int) -> str | None:
    if step_count >= budget.max_steps:
        return f"max_steps ({budget.max_steps}) reached"
    if budget.max_input_tokens is not None and totals.input_tokens >= budget.max_input_tokens:
        return f"max_input_tokens ({budget.max_input_tokens}) reached"
    if budget.max_output_tokens is not None and totals.output_tokens >= budget.max_output_tokens:
        return f"max_output_tokens ({budget.max_output_tokens}) reached"
    if budget.max_wall_time_ms is not None and totals.wall_time_ms >= budget.max_wall_time_ms:
        return f"max_wall_time_ms ({budget.max_wall_time_ms}) reached"
    if budget.max_cost_usd is not None and totals.cost_usd >= budget.max_cost_usd:
        return f"max_cost_usd ({budget.max_cost_usd}) reached"
    return None


def _serialize_tool_output(output: object, error: str | None) -> str:
    if error is not None:
        return json.dumps({"error": error})
    if isinstance(output, str):
        return output
    try:
        return json.dumps(output, default=str)
    except (TypeError, ValueError):
        return str(output)


async def run_agent(
    provider: ChatProvider,
    *,
    system: str | None,
    user_prompt: str,
    tools: dict[str, Tool],
    budget: Budget,
    max_tokens: int = 4096,
    temperature: float = 0.0,
) -> LoopOutcome:
    """Run an agent loop. Returns the full step trace and rolled-up totals."""

    tool_defs = [
        ToolDefinition(name=t.name, description=t.description, input_schema=t.input_schema)
        for t in tools.values()
    ]
    messages: list[ChatMessage] = []
    if system:
        messages.append(ChatMessage(role="system", content=system))
    messages.append(ChatMessage(role="user", content=user_prompt))

    steps: list[Step] = []
    totals = Totals()
    behavior_flags: list[str] = []
    loop_started = time.perf_counter()

    while True:
        # Gate budget *before* each turn so a hit is reported instead of going silent.
        why = _budget_exceeded(totals, budget, len(steps))
        if why is not None:
            return LoopOutcome(
                status=RunStatus.BUDGET_EXCEEDED,
                steps=steps,
                totals=totals,
                error=why,
                behavior_flags=behavior_flags,
            )

        turn_started = time.perf_counter()
        try:
            response = await provider.chat(
                messages,
                tool_defs,
                max_tokens=max_tokens,
                temperature=temperature,
            )
        except Exception as exc:  # noqa: BLE001 - surface raw error in trace
            return LoopOutcome(
                status=RunStatus.ERROR,
                steps=steps,
                totals=totals,
                error=f"provider error: {exc!r}",
                behavior_flags=behavior_flags,
            )
        model_elapsed_ms = (time.perf_counter() - turn_started) * 1000

        totals.input_tokens += response.usage.input_tokens
        totals.output_tokens += response.usage.output_tokens
        totals.cached_tokens += response.usage.cached_input_tokens
        totals.cost_usd = compute_cost(provider.config.provider, provider.config.model, totals)
        totals.wall_time_ms = (time.perf_counter() - loop_started) * 1000
        if totals.time_to_first_token_ms is None:
            totals.time_to_first_token_ms = response.latency_ms or model_elapsed_ms

        # Execute every tool the model requested on this turn, recording each result.
        tool_traces: list[ToolCallTrace] = []
        for call in response.tool_calls:
            tool = tools.get(call.name)
            tool_started = time.perf_counter()
            output: object = None
            err: str | None = None
            if tool is None:
                err = f"unknown tool: {call.name}"
                if "hallucinated_tool" not in behavior_flags:
                    behavior_flags.append("hallucinated_tool")
            else:
                try:
                    output = await tool.run(**call.arguments)
                except ToolError as e:
                    err = str(e)
                except Exception as e:  # noqa: BLE001 - surface raw error in trace
                    err = f"tool exception: {e!r}"
            tool_traces.append(
                ToolCallTrace(
                    name=call.name,
                    input=call.arguments,
                    output=output,
                    duration_ms=(time.perf_counter() - tool_started) * 1000,
                    error=err,
                )
            )
            totals.tool_call_count += 1

        steps.append(
            Step(
                step_id=len(steps),
                role=StepRole.ASSISTANT,
                content=response.content,
                tool_calls=tool_traces,
                tokens=StepTokens(
                    input=response.usage.input_tokens,
                    output=response.usage.output_tokens,
                    cached=response.usage.cached_input_tokens,
                ),
                timing_ms=model_elapsed_ms,
            )
        )

        # Update message history: the assistant turn, then one tool message per call.
        messages.append(
            ChatMessage(
                role="assistant",
                content=response.content,
                tool_calls=response.tool_calls,
            )
        )
        for call, trace in zip(response.tool_calls, tool_traces):
            messages.append(
                ChatMessage(
                    role="tool",
                    content=_serialize_tool_output(trace.output, trace.error),
                    tool_call_id=call.id,
                )
            )

        if response.stop_reason != StopReason.TOOL_USE or not response.tool_calls:
            return LoopOutcome(
                status=RunStatus.SUCCESS,
                steps=steps,
                totals=totals,
                behavior_flags=behavior_flags,
            )
