import pytest

from llmbench.tools.base import ToolError
from llmbench.tools.fake_sql import FakeSql, build_fake_sql_tools


def _seeded_state() -> FakeSql:
    state = FakeSql()
    state.execute_setup("CREATE TABLE users (id INT, name TEXT)")
    state.execute_setup("INSERT INTO users VALUES (1, 'alice')")
    state.execute_setup("INSERT INTO users VALUES (2, 'bob')")
    return state


@pytest.mark.asyncio
async def test_execute_setup_creates_schema():
    state = _seeded_state()
    tools = build_fake_sql_tools(state)
    result = await tools["sql_query"].run(sql="SELECT * FROM users")
    assert result["rowcount"] == 2
    assert all(isinstance(r, dict) for r in result["rows"])


@pytest.mark.asyncio
async def test_insert_returns_rowcount_and_lastrowid():
    state = _seeded_state()
    tools = build_fake_sql_tools(state)
    result = await tools["sql_insert"].run(
        sql="INSERT INTO users VALUES (?, ?)", params=[3, "carol"]
    )
    assert result["rowcount"] == 1
    assert result["lastrowid"] is not None
    query = await tools["sql_query"].run(sql="SELECT * FROM users WHERE id=3")
    assert query["rowcount"] == 1
    assert query["rows"][0]["name"] == "carol"


@pytest.mark.asyncio
async def test_update_returns_affected_rowcount():
    state = _seeded_state()
    tools = build_fake_sql_tools(state)
    result = await tools["sql_update"].run(
        sql="UPDATE users SET name=? WHERE id=?", params=["updated", 1]
    )
    assert result["rowcount"] == 1
    query = await tools["sql_query"].run(sql="SELECT name FROM users WHERE id=1")
    assert query["rows"][0]["name"] == "updated"


@pytest.mark.asyncio
async def test_delete_via_sql_update_tool():
    state = _seeded_state()
    tools = build_fake_sql_tools(state)
    result = await tools["sql_update"].run(sql="DELETE FROM users WHERE id=1")
    assert result["rowcount"] > 0
    query = await tools["sql_query"].run(sql="SELECT * FROM users WHERE id=1")
    assert query["rowcount"] == 0


@pytest.mark.asyncio
async def test_sql_query_rejects_non_select():
    state = _seeded_state()
    tools = build_fake_sql_tools(state)
    with pytest.raises(ToolError, match="sql_query only accepts SELECT"):
        await tools["sql_query"].run(sql="INSERT INTO users VALUES (9, 'x')")


@pytest.mark.asyncio
async def test_sql_insert_rejects_non_insert():
    state = _seeded_state()
    tools = build_fake_sql_tools(state)
    with pytest.raises(ToolError, match="sql_insert only accepts INSERT"):
        await tools["sql_insert"].run(sql="SELECT * FROM users")


@pytest.mark.asyncio
async def test_sqlite3_errors_surface_as_tool_error():
    state = FakeSql()
    tools = build_fake_sql_tools(state)
    with pytest.raises(ToolError):
        await tools["sql_query"].run(sql="SELECT * FROM nonexistent_table")
    assert len(state.calls) == 1
    assert state.calls[0]["error"] is not None


@pytest.mark.asyncio
async def test_calls_are_recorded():
    state = _seeded_state()
    tools = build_fake_sql_tools(state)
    await tools["sql_query"].run(sql="SELECT * FROM users")
    await tools["sql_insert"].run(sql="INSERT INTO users VALUES (?, ?)", params=[4, "dan"])
    await tools["sql_update"].run(sql="UPDATE users SET name=? WHERE id=?", params=["dave", 4])
    assert len(state.calls) == 3
    assert state.calls[0]["operation"] == "sql_query"
    assert state.calls[1]["operation"] == "sql_insert"
    assert state.calls[2]["operation"] == "sql_update"
    assert all(c["error"] is None for c in state.calls)


@pytest.mark.asyncio
async def test_build_fake_sql_tools_returns_three_tools_on_same_state():
    state = FakeSql()
    tools = build_fake_sql_tools(state)
    assert set(tools.keys()) == {"sql_query", "sql_insert", "sql_update"}
    assert tools["sql_query"]._state is state
    assert tools["sql_insert"]._state is state
    assert tools["sql_update"]._state is state
