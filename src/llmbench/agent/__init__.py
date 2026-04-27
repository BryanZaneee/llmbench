"""Agentic v1 engine: provider-agnostic loop that drives a chat model with tools.

The loop sends messages, receives content + tool_calls, executes the tools
in-process, appends results, and repeats until the model emits a non-tool stop
reason or the configured Budget is exhausted. See llmbench-prd.md for the
JSON-trace contract this engine emits.
"""

from __future__ import annotations

from .loop import LoopOutcome, run_agent
from .provider import (
    ChatMessage,
    ChatProvider,
    ChatResponse,
    StopReason,
    ToolCallRequest,
    ToolDefinition,
)
from .runner import run_task

__all__ = [
    "ChatMessage",
    "ChatProvider",
    "ChatResponse",
    "LoopOutcome",
    "StopReason",
    "ToolCallRequest",
    "ToolDefinition",
    "run_agent",
    "run_task",
]
