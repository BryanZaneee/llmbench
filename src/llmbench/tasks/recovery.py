"""recovery task: insert an audit row via commit_transaction with transient failure.

The agent must call commit_transaction with action="login" and user_id=42. The first
call always fails with a transaction conflict error; the model must retry with the
same arguments to pass.
"""

from __future__ import annotations

from ..schema import Budget, VerdictResult
from ..tools.fake_sql import FakeSql, SqlInsertTool
from ..tools.failure_injector import FailureInjector
from .base import Task, TaskCheckResult, TaskSetup, register_task

_SYSTEM = (
    "You are a database agent. You have one tool: commit_transaction. "
    "If it fails with a transient error, retry the same call with identical arguments."
)

_USER_PROMPT = (
    "Commit an audit log entry using commit_transaction. "
    "Insert a row with action=\"login\" and user_id=42 into the audit table. "
    "Use exactly this SQL and params: "
    "sql=\"INSERT INTO audit (action, user_id) VALUES (?, ?)\", params=[\"login\", 42]. "
    "If you receive a transient error, retry the same insert with the same arguments. "
    "Stop once the row is committed."
)


@register_task
class RecoveryTask(Task):
    id = "recovery"
    version = "1.0.0"
    description = "Insert an audit row via commit_transaction; the first call fails -- the model must retry."

    def setup(self) -> TaskSetup:
        state = FakeSql()
        state.execute_setup(
            "CREATE TABLE audit ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "action TEXT NOT NULL, "
            "user_id INTEGER NOT NULL"
            ")"
        )

        inner = SqlInsertTool(state)
        wrapped = FailureInjector(
            inner,
            fail_times=1,
            error_message="transaction conflict: please retry with the same arguments",
        )
        wrapped.name = "commit_transaction"
        wrapped.description = (
            "Commit an audit-log entry into the audit table. "
            "May fail transiently with a 'transaction conflict' error; "
            "retry the same insert if that happens."
        )

        self.sql = state
        self.tool = wrapped

        return TaskSetup(
            system=_SYSTEM,
            user_prompt=_USER_PROMPT,
            tools={"commit_transaction": wrapped},
            budget=Budget(max_steps=8),
        )

    def check(self) -> TaskCheckResult:
        rows = list(self.sql._conn.execute("SELECT action, user_id FROM audit").fetchall())

        if len(rows) == 0:
            return TaskCheckResult(
                verdict=VerdictResult.FAIL,
                detail="model did not commit the row",
            )

        if len(rows) > 1:
            return TaskCheckResult(
                verdict=VerdictResult.FAIL,
                detail="model committed extra rows",
            )

        row = rows[0]
        if row["action"] != "login" or row["user_id"] != 42:
            return TaskCheckResult(
                verdict=VerdictResult.FAIL,
                detail=f"wrong values: action={row['action']!r}, user_id={row['user_id']!r}",
            )

        flags: list[str] = []
        # _remaining_failures == 0 means the injector fired at least once; combined with a
        # committed row, the model successfully recovered from the transient failure.
        if self.tool._remaining_failures == 0:
            flags.append("recovered_from_transient_failure")

        return TaskCheckResult(verdict=VerdictResult.PASS, behavior_flags=flags)
