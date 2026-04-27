import pytest

from llmbench.tools.base import Tool, ToolError
from llmbench.tools.failure_injector import AlwaysFailTool, FailureInjector


class SuccessTool(Tool):
    name = "ok"
    description = "Always returns ok."
    input_schema = {"type": "object", "properties": {}, "required": []}

    async def run(self, **kwargs):
        return "ok"


@pytest.mark.asyncio
async def test_failure_injector_fails_n_times_then_succeeds():
    wrapped = FailureInjector(SuccessTool(), fail_times=2, error_message="nope")
    with pytest.raises(ToolError, match="nope"):
        await wrapped.run()
    with pytest.raises(ToolError, match="nope"):
        await wrapped.run()
    assert await wrapped.run() == "ok"


@pytest.mark.asyncio
async def test_failure_injector_mirrors_inner_surface():
    inner = SuccessTool()
    wrapped = FailureInjector(inner, fail_times=0)
    assert wrapped.name == inner.name
    assert wrapped.description == inner.description
    assert wrapped.input_schema == inner.input_schema


@pytest.mark.asyncio
async def test_always_fail_tool_always_raises():
    tool = AlwaysFailTool(name="dead", description="dead tool")
    for _ in range(3):
        with pytest.raises(ToolError):
            await tool.run()
