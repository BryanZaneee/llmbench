"""Sandboxed tool primitives for agentic tasks plus the failure-injection wrapper."""

from __future__ import annotations

from .base import Tool, ToolError
from .fake_fs import (
    DeleteFileTool,
    FakeFs,
    ListDirTool,
    ReadFileTool,
    WriteFileTool,
    build_fake_fs_tools,
)
from .failure_injector import AlwaysFailTool, FailureInjector

__all__ = [
    "AlwaysFailTool",
    "DeleteFileTool",
    "FailureInjector",
    "FakeFs",
    "ListDirTool",
    "ReadFileTool",
    "Tool",
    "ToolError",
    "WriteFileTool",
    "build_fake_fs_tools",
]
