"""In-memory SQLite tool primitive.

Exposes `sql_query`, `sql_insert`, and `sql_update` as three Tool instances
that share a single in-memory SQLite connection (FakeSql). Tasks seed the
schema at setup() time via execute_setup(); verdicts inspect state.calls.
"""

from __future__ import annotations

import sqlite3
from typing import Any

from .base import Tool, ToolError


class FakeSql:
    """Wraps a fresh in-memory SQLite connection shared by the three SQL tools."""

    def __init__(self) -> None:
        self._conn = sqlite3.connect(":memory:")
        self._conn.row_factory = sqlite3.Row
        self.calls: list[dict[str, Any]] = []

    def execute_setup(self, sql: str) -> None:
        """Execute a DDL or seed statement without recording it as a model action."""
        self._conn.execute(sql)
        self._conn.commit()

    def record_call(
        self,
        operation: str,
        sql: str,
        params: list | dict | None,
        rowcount: int,
        error: str | None,
    ) -> None:
        self.calls.append(
            {
                "operation": operation,
                "sql": sql,
                "params": params,
                "rowcount": rowcount,
                "error": error,
            }
        )

    def close(self) -> None:
        self._conn.close()


def _strip_leading(sql: str) -> str:
    """Return sql with leading whitespace and open-parens removed, uppercased."""
    return sql.lstrip(" \t\n\r(").upper()


class SqlQueryTool(Tool):
    name = "sql_query"
    description = "Run a read-only SQL SELECT and return the resulting rows. Returns {rows: list, rowcount: int}."
    input_schema = {
        "type": "object",
        "properties": {
            "sql": {"type": "string", "description": "SELECT statement to execute."},
            "params": {
                "type": "array",
                "description": "Positional parameters bound to ? placeholders.",
                "default": [],
            },
        },
        "required": ["sql"],
    }

    def __init__(self, state: FakeSql) -> None:
        self._state = state

    async def run(self, *, sql: str, params: list | None = None) -> dict[str, Any]:
        if not _strip_leading(sql).startswith("SELECT"):
            raise ToolError("sql_query only accepts SELECT")
        p = params or []
        try:
            cur = self._state._conn.execute(sql, p)
            rows = [dict(r) for r in cur.fetchall()]
        except sqlite3.Error as exc:
            self._state.record_call("sql_query", sql, params, 0, str(exc))
            raise ToolError(str(exc)) from exc
        self._state.record_call("sql_query", sql, params, len(rows), None)
        return {"rows": rows, "rowcount": len(rows)}


class SqlInsertTool(Tool):
    name = "sql_insert"
    description = "Run an INSERT and return the number of rows inserted."
    input_schema = {
        "type": "object",
        "properties": {
            "sql": {"type": "string", "description": "INSERT statement to execute."},
            "params": {
                "type": "array",
                "description": "Positional parameters bound to ? placeholders.",
                "default": [],
            },
        },
        "required": ["sql"],
    }

    def __init__(self, state: FakeSql) -> None:
        self._state = state

    async def run(self, *, sql: str, params: list | None = None) -> dict[str, Any]:
        if not _strip_leading(sql).startswith("INSERT"):
            raise ToolError("sql_insert only accepts INSERT")
        p = params or []
        try:
            cur = self._state._conn.execute(sql, p)
            self._state._conn.commit()
        except sqlite3.Error as exc:
            self._state.record_call("sql_insert", sql, params, 0, str(exc))
            raise ToolError(str(exc)) from exc
        self._state.record_call("sql_insert", sql, params, cur.rowcount, None)
        return {"rowcount": cur.rowcount, "lastrowid": cur.lastrowid}


class SqlUpdateTool(Tool):
    name = "sql_update"
    description = "Run an UPDATE or DELETE and return the number of rows affected."
    input_schema = {
        "type": "object",
        "properties": {
            "sql": {"type": "string", "description": "UPDATE or DELETE statement to execute."},
            "params": {
                "type": "array",
                "description": "Positional parameters bound to ? placeholders.",
                "default": [],
            },
        },
        "required": ["sql"],
    }

    def __init__(self, state: FakeSql) -> None:
        self._state = state

    async def run(self, *, sql: str, params: list | None = None) -> dict[str, Any]:
        stripped = _strip_leading(sql)
        if not (stripped.startswith("UPDATE") or stripped.startswith("DELETE")):
            raise ToolError("sql_update only accepts UPDATE or DELETE")
        p = params or []
        try:
            cur = self._state._conn.execute(sql, p)
            self._state._conn.commit()
        except sqlite3.Error as exc:
            self._state.record_call("sql_update", sql, params, 0, str(exc))
            raise ToolError(str(exc)) from exc
        self._state.record_call("sql_update", sql, params, cur.rowcount, None)
        return {"rowcount": cur.rowcount}


def build_fake_sql_tools(state: FakeSql) -> dict[str, Tool]:
    """Construct the canonical fake_sql tool set bound to a single FakeSql."""
    return {t.name: t for t in (SqlQueryTool(state), SqlInsertTool(state), SqlUpdateTool(state))}
