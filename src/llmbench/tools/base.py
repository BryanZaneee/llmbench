"""Tool contract. A tool is a Python callable surfaced to the model with a JSON schema.

Concrete primitives (fake_fs, fake_http, ...) live alongside this base. The agent
loop receives a dict[str, Tool] and routes each model tool_call to the matching
entry. Raise ToolError from inside `run` to signal a failure that should be
reported back to the model rather than killing the run.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class ToolError(Exception):
    """Raised by a tool to signal a failure that should be surfaced to the model."""


class Tool(ABC):
    name: str
    description: str
    input_schema: dict[str, Any]

    @abstractmethod
    async def run(self, **kwargs: Any) -> Any:
        """Execute the tool. The return value is JSON-serialized into the tool message."""
