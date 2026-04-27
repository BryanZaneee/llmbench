"""Sandboxed shell tool primitive.

Exposes `run_command` as a single Tool instance backed by a FakeShell allowlist.
Tasks register exact command strings with canned outputs at setup() time; the model
discovers the boundary by calling commands and observing 126 for disallowed ones.
No subprocess, no os.system -- this is a pure lookup table.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .base import Tool


@dataclass
class _CommandEntry:
    stdout: str
    stderr: str
    exit_code: int


@dataclass
class _CallRecord:
    command: str
    allowed: bool
    exit_code: int


@dataclass
class FakeShell:
    """Holds the allowlist and call history for the sandboxed shell."""

    _allowlist: dict[str, _CommandEntry] = field(default_factory=dict)
    calls: list[_CallRecord] = field(default_factory=list)

    def register(
        self,
        command: str,
        *,
        stdout: str = "",
        stderr: str = "",
        exit_code: int = 0,
    ) -> None:
        self._allowlist[command] = _CommandEntry(stdout=stdout, stderr=stderr, exit_code=exit_code)

    def record_call(self, command: str, allowed: bool, exit_code: int) -> None:
        self.calls.append(_CallRecord(command=command, allowed=allowed, exit_code=exit_code))


class RunCommandTool(Tool):
    name = "run_command"
    description = "Run a shell command from the allowlist. Returns {stdout, stderr, exit_code}."
    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "command": {"type": "string", "description": "Exact command line to run."}
        },
        "required": ["command"],
    }

    def __init__(self, shell: FakeShell) -> None:
        self._shell = shell

    async def run(self, *, command: str) -> dict[str, Any]:
        entry = self._shell._allowlist.get(command)
        if entry is not None:
            self._shell.record_call(command, allowed=True, exit_code=entry.exit_code)
            return {"stdout": entry.stdout, "stderr": entry.stderr, "exit_code": entry.exit_code}
        # 126 mirrors POSIX "permission denied" -- the command exists but is not allowed.
        self._shell.record_call(command, allowed=False, exit_code=126)
        return {"stdout": "", "stderr": f"command not allowed: {command}", "exit_code": 126}


def build_fake_shell_tools(state: FakeShell) -> dict[str, Tool]:
    """Construct the fake_shell tool set bound to a single FakeShell."""
    tool = RunCommandTool(state)
    return {tool.name: tool}
