import pytest

from llmbench.tools.fake_shell import FakeShell, build_fake_shell_tools


@pytest.mark.asyncio
async def test_allowlisted_command_returns_canned_output():
    state = FakeShell()
    state.register("ls /etc", stdout="hosts\npasswd\n", stderr="", exit_code=0)
    tools = build_fake_shell_tools(state)
    result = await tools["run_command"].run(command="ls /etc")
    assert result["stdout"] == "hosts\npasswd\n"
    assert result["stderr"] == ""
    assert result["exit_code"] == 0


@pytest.mark.asyncio
async def test_disallowed_command_returns_126():
    state = FakeShell()
    tools = build_fake_shell_tools(state)
    result = await tools["run_command"].run(command="rm -rf /")
    assert result["exit_code"] == 126
    assert "rm -rf /" in result["stderr"]
    assert result["stdout"] == ""


@pytest.mark.asyncio
async def test_distinct_outputs_per_command():
    state = FakeShell()
    state.register("git status", stdout="On branch main\n", exit_code=0)
    state.register("git log --oneline", stdout="abc1234 first commit\n", exit_code=0)
    tools = build_fake_shell_tools(state)
    r1 = await tools["run_command"].run(command="git status")
    r2 = await tools["run_command"].run(command="git log --oneline")
    assert r1["stdout"] == "On branch main\n"
    assert r2["stdout"] == "abc1234 first commit\n"


@pytest.mark.asyncio
async def test_calls_accumulate_in_order():
    state = FakeShell()
    state.register("echo hi", stdout="hi\n")
    tools = build_fake_shell_tools(state)
    await tools["run_command"].run(command="echo hi")
    await tools["run_command"].run(command="not registered")
    await tools["run_command"].run(command="echo hi")
    assert len(state.calls) == 3
    assert state.calls[0].allowed is True
    assert state.calls[0].command == "echo hi"
    assert state.calls[1].allowed is False
    assert state.calls[1].command == "not registered"
    assert state.calls[2].allowed is True


@pytest.mark.asyncio
async def test_empty_stdout_stderr_defaults():
    state = FakeShell()
    state.register("true")
    tools = build_fake_shell_tools(state)
    result = await tools["run_command"].run(command="true")
    assert result["stdout"] == ""
    assert result["stderr"] == ""
    assert result["exit_code"] == 0


@pytest.mark.asyncio
async def test_build_fake_shell_tools_wires_tool():
    state = FakeShell()
    state.register("pwd", stdout="/home/user\n")
    tools = build_fake_shell_tools(state)
    assert "run_command" in tools
    result = await tools["run_command"].run(command="pwd")
    assert result["stdout"] == "/home/user\n"
