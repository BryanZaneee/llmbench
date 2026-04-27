"""In-memory filesystem tool primitive.

Exposes `read_file`, `write_file`, `list_dir`, and `delete_file` as four Tool
instances that share a single in-memory dict (FakeFs). Tasks seed the FS at
`setup()` time; check() inspects the post-run state on the same FakeFs.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .base import Tool, ToolError


@dataclass
class FakeFs:
    files: dict[str, str] = field(default_factory=dict)

    def read(self, path: str) -> str:
        if path not in self.files:
            raise ToolError(f"file not found: {path}")
        return self.files[path]

    def write(self, path: str, content: str) -> None:
        self.files[path] = content

    def delete(self, path: str) -> None:
        if path not in self.files:
            raise ToolError(f"file not found: {path}")
        del self.files[path]

    def list(self, prefix: str = "") -> list[str]:
        return sorted(p for p in self.files if p.startswith(prefix))


class ReadFileTool(Tool):
    name = "read_file"
    description = "Read the contents of a file. Returns the file as a single string."
    input_schema = {
        "type": "object",
        "properties": {"path": {"type": "string", "description": "Path to read."}},
        "required": ["path"],
    }

    def __init__(self, fs: FakeFs):
        self._fs = fs

    async def run(self, *, path: str) -> str:
        return self._fs.read(path)


class WriteFileTool(Tool):
    name = "write_file"
    description = "Write content to a file. Creates the file if it does not exist; overwrites otherwise."
    input_schema = {
        "type": "object",
        "properties": {
            "path": {"type": "string"},
            "content": {"type": "string"},
        },
        "required": ["path", "content"],
    }

    def __init__(self, fs: FakeFs):
        self._fs = fs

    async def run(self, *, path: str, content: str) -> str:
        self._fs.write(path, content)
        return f"wrote {len(content)} chars to {path}"


class ListDirTool(Tool):
    name = "list_dir"
    description = "List file paths, optionally filtered by a path prefix. Pass an empty prefix to list all."
    input_schema = {
        "type": "object",
        "properties": {
            "prefix": {"type": "string", "description": "Path prefix filter; empty string returns every path."}
        },
        "required": [],
    }

    def __init__(self, fs: FakeFs):
        self._fs = fs

    async def run(self, *, prefix: str = "") -> list[str]:
        return self._fs.list(prefix)


class DeleteFileTool(Tool):
    name = "delete_file"
    description = "Delete a file. Errors if the path does not exist."
    input_schema = {
        "type": "object",
        "properties": {"path": {"type": "string"}},
        "required": ["path"],
    }

    def __init__(self, fs: FakeFs):
        self._fs = fs

    async def run(self, *, path: str) -> str:
        self._fs.delete(path)
        return f"deleted {path}"


def build_fake_fs_tools(fs: FakeFs) -> dict[str, Tool]:
    """Construct the canonical fake_fs tool set bound to a single FakeFs."""
    return {
        t.name: t
        for t in (ReadFileTool(fs), WriteFileTool(fs), ListDirTool(fs), DeleteFileTool(fs))
    }
