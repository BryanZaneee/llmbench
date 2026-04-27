"""file-refactor task: rename a function across a 5-file mock project.

The agent must rename `process_data` to `transform_data` in every file. Success
requires zero remaining occurrences of the old name across files that originally
contained it, and every Python file still parsing cleanly.
"""

from __future__ import annotations

import ast

from ..schema import Budget, VerdictResult
from ..tools.fake_fs import FakeFs, build_fake_fs_tools
from .base import Task, TaskCheckResult, TaskSetup, register_task

_INITIAL_FILES: dict[str, str] = {
    "src/ingest.py": (
        "def process_data(rows):\n"
        "    return [r for r in rows if r]\n"
    ),
    "src/pipeline.py": (
        "from .ingest import process_data\n"
        "\n"
        "def run(rows):\n"
        "    cleaned = process_data(rows)\n"
        "    return cleaned\n"
    ),
    "src/cli.py": (
        "from .pipeline import run\n"
        "from .ingest import process_data\n"
        "\n"
        "def main(rows):\n"
        "    return run(rows)\n"
    ),
    "tests/test_pipeline.py": (
        "from src.ingest import process_data\n"
        "from src.pipeline import run\n"
        "\n"
        "def test_run():\n"
        "    assert run([1, 2, 3]) == [1, 2, 3]\n"
        "\n"
        "def test_process_data_drops_falsy():\n"
        "    assert process_data([0, 1, None, 2]) == [1, 2]\n"
    ),
    "README.md": (
        "# pipeline\n"
        "\n"
        "Use `process_data` to clean rows before calling `run`.\n"
    ),
}

_USER_PROMPT = (
    "Rename the function `process_data` to `transform_data` across every file in the "
    "project. Use `list_dir` to discover files, `read_file` to inspect each one, and "
    "`write_file` to commit changes. Update all call sites, all imports, and every "
    "documentation reference. When you are confident every occurrence is renamed and "
    "all Python files still parse, stop responding."
)

_SYSTEM = (
    "You are a refactoring agent operating inside an in-memory project sandbox. Use "
    "the provided tools to read and modify files. Be exhaustive: missed references "
    "break the build."
)


@register_task
class FileRefactorTask(Task):
    id = "file-refactor"
    version = "1.0.0"
    description = "Rename `process_data` to `transform_data` across a 5-file mock project."

    def __init__(self) -> None:
        self._fs = FakeFs(files=dict(_INITIAL_FILES))

    def setup(self) -> TaskSetup:
        return TaskSetup(
            system=_SYSTEM,
            user_prompt=_USER_PROMPT,
            tools=build_fake_fs_tools(self._fs),
            budget=Budget(max_steps=30),
        )

    def check(self) -> TaskCheckResult:
        expected_renamed = [p for p, c in _INITIAL_FILES.items() if "process_data" in c]
        for path in expected_renamed:
            if path not in self._fs.files:
                return TaskCheckResult(
                    verdict=VerdictResult.FAIL,
                    detail=f"file deleted: {path}",
                )
            content = self._fs.files[path]
            if "process_data" in content:
                return TaskCheckResult(
                    verdict=VerdictResult.FAIL,
                    detail=f"old name `process_data` still present in {path}",
                )
            if "transform_data" not in content:
                return TaskCheckResult(
                    verdict=VerdictResult.FAIL,
                    detail=f"new name `transform_data` missing in {path}",
                )

        for path, content in self._fs.files.items():
            if path.endswith(".py"):
                try:
                    ast.parse(content)
                except SyntaxError as e:
                    return TaskCheckResult(
                        verdict=VerdictResult.FAIL,
                        detail=f"syntax error in {path}: {e}",
                    )

        return TaskCheckResult(verdict=VerdictResult.PASS)
