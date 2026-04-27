"""Built-in agentic tasks for the v1 suite.

Importing each task module triggers its `@register_task` decorator so the
registry is populated by the time `get_task` / `list_tasks` are called.
"""

from __future__ import annotations

from . import api_orchestration  # noqa: F401  -- import for side-effect (registry)
from . import file_refactor  # noqa: F401  -- import for side-effect (registry)
from . import long_horizon  # noqa: F401  -- import for side-effect (registry)
from . import multi_step_research  # noqa: F401  -- import for side-effect (registry)
from . import recovery  # noqa: F401  -- import for side-effect (registry)
from .base import Task, TaskCheckResult, TaskSetup, get_task, list_tasks, register_task

__all__ = [
    "Task",
    "TaskCheckResult",
    "TaskSetup",
    "get_task",
    "list_tasks",
    "register_task",
]
