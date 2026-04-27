"""Failure-injection wrappers used by the recovery task and similar fault-tolerance tests.

`FailureInjector` wraps any Tool, raising ToolError for the first N calls then
delegating to the inner tool. `AlwaysFailTool` is a standalone tool that errors
on every invocation; useful when a task wants the model to recover from a
permanently-broken capability.
"""

from __future__ import annotations

from typing import Any

from .base import Tool, ToolError


class FailureInjector(Tool):
    """Wraps another Tool, raising ToolError for the first `fail_times` invocations."""

    def __init__(self, inner: Tool, *, fail_times: int, error_message: str = "transient failure"):
        self.inner = inner
        self._remaining_failures = fail_times
        self._error_message = error_message

        # Mirror the inner tool's surface so the model sees no behavioral wrapper.
        self.name = inner.name
        self.description = inner.description
        self.input_schema = inner.input_schema

    async def run(self, **kwargs: Any) -> Any:
        if self._remaining_failures > 0:
            self._remaining_failures -= 1
            raise ToolError(self._error_message)
        return await self.inner.run(**kwargs)


class AlwaysFailTool(Tool):
    """A tool that always raises ToolError. Pair with a real tool for recovery scenarios."""

    def __init__(self, name: str, description: str, error_message: str = "this tool always fails"):
        self.name = name
        self.description = description
        self.input_schema = {"type": "object", "properties": {}, "required": []}
        self._error_message = error_message

    async def run(self, **kwargs: Any) -> Any:
        raise ToolError(self._error_message)
