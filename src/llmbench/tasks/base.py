"""Task contract + registry. A task is one canonical scenario the agent runs.

Each Task instance is stateful and single-use: `setup()` builds a fresh sandbox
and prompt; `check()` inspects the post-run state on the same instance. The
runner instantiates a new Task per repetition.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from ..schema import Budget, VerdictResult
from ..tools.base import Tool


@dataclass
class TaskSetup:
    """What a task hands the agent loop: prompt, tools, budget."""

    system: str | None
    user_prompt: str
    tools: dict[str, Tool]
    budget: Budget


@dataclass
class TaskCheckResult:
    verdict: VerdictResult
    detail: str = ""
    behavior_flags: list[str] = field(default_factory=list)


class Task(ABC):
    """Stateful scenario for one (task, model, repetition). Do not reuse instances."""

    id: str
    version: str
    description: str

    @abstractmethod
    def setup(self) -> TaskSetup:
        """Build a fresh sandbox for one run."""

    @abstractmethod
    def check(self) -> TaskCheckResult:
        """Inspect the final sandbox state. Returns pass/fail + optional behavior flags."""


_REGISTRY: dict[str, type[Task]] = {}


def register_task(cls: type[Task]) -> type[Task]:
    """Decorator: registers a Task subclass under its `id`."""
    if not getattr(cls, "id", None):
        raise ValueError(f"Task {cls.__name__} must set a class-level `id`")
    if cls.id in _REGISTRY and _REGISTRY[cls.id] is not cls:
        raise ValueError(f"Task id collision: {cls.id}")
    _REGISTRY[cls.id] = cls
    return cls


def get_task(task_id: str) -> Task:
    if task_id not in _REGISTRY:
        raise KeyError(f"unknown task: {task_id}. registered: {sorted(_REGISTRY)}")
    return _REGISTRY[task_id]()


def list_tasks() -> list[type[Task]]:
    return [_REGISTRY[k] for k in sorted(_REGISTRY)]
