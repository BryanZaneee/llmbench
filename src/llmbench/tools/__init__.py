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
from .fake_http import FakeHttp, HttpGetTool, HttpPostTool, build_fake_http_tools
from .fake_search import FakeSearch, SearchTool, build_fake_search_tools
from .fake_shell import FakeShell, RunCommandTool, build_fake_shell_tools
from .fake_sql import (
    FakeSql,
    SqlInsertTool,
    SqlQueryTool,
    SqlUpdateTool,
    build_fake_sql_tools,
)
from .failure_injector import AlwaysFailTool, FailureInjector

__all__ = [
    "AlwaysFailTool",
    "DeleteFileTool",
    "FailureInjector",
    "FakeFs",
    "FakeHttp",
    "FakeSearch",
    "FakeShell",
    "FakeSql",
    "HttpGetTool",
    "HttpPostTool",
    "ListDirTool",
    "ReadFileTool",
    "RunCommandTool",
    "SearchTool",
    "SqlInsertTool",
    "SqlQueryTool",
    "SqlUpdateTool",
    "Tool",
    "ToolError",
    "WriteFileTool",
    "build_fake_fs_tools",
    "build_fake_http_tools",
    "build_fake_search_tools",
    "build_fake_shell_tools",
    "build_fake_sql_tools",
]
