import pytest

from llmbench.agent import (
    ChatResponse,
    StopReason,
    ToolCallRequest,
    run_agent,
)
from llmbench.agent.providers.mock import MockProvider
from llmbench.schema import Budget, ModelConfig, RunStatus, TokenUsage
from llmbench.tools.base import Tool


class EchoTool(Tool):
    name = "echo"
    description = "Echo the given text back."
    input_schema = {
        "type": "object",
        "properties": {"text": {"type": "string"}},
        "required": ["text"],
    }

    async def run(self, *, text: str) -> str:
        return text


@pytest.mark.asyncio
async def test_loop_terminates_on_end_turn():
    provider = MockProvider(ModelConfig(provider="mock", model="m")).script(
        ChatResponse(
            content="all done",
            tool_calls=[],
            usage=TokenUsage(input_tokens=10, output_tokens=2),
            stop_reason=StopReason.END_TURN,
        )
    )
    result = await run_agent(
        provider,
        system=None,
        user_prompt="hi",
        tools={},
        budget=Budget(max_steps=5),
    )
    assert result.status == RunStatus.SUCCESS
    assert len(result.steps) == 1
    assert result.steps[0].content == "all done"
    assert result.totals.input_tokens == 10
    assert result.totals.output_tokens == 2
    assert result.totals.tool_call_count == 0


@pytest.mark.asyncio
async def test_loop_executes_tool_then_finishes():
    provider = MockProvider(ModelConfig(provider="mock", model="m")).script(
        ChatResponse(
            content=None,
            tool_calls=[ToolCallRequest(id="t1", name="echo", arguments={"text": "hello"})],
            usage=TokenUsage(input_tokens=5, output_tokens=3),
            stop_reason=StopReason.TOOL_USE,
        ),
        ChatResponse(
            content="echo said hello",
            tool_calls=[],
            usage=TokenUsage(input_tokens=8, output_tokens=4),
            stop_reason=StopReason.END_TURN,
        ),
    )
    tools: dict[str, Tool] = {"echo": EchoTool()}

    result = await run_agent(
        provider,
        system=None,
        user_prompt="please echo hello",
        tools=tools,
        budget=Budget(max_steps=10),
    )
    assert result.status == RunStatus.SUCCESS
    # One step per provider turn; the tool call lives inside the assistant step.
    assert len(result.steps) == 2
    first = result.steps[0]
    assert first.tool_calls[0].name == "echo"
    assert first.tool_calls[0].output == "hello"
    assert first.tool_calls[0].error is None
    assert result.totals.tool_call_count == 1
    assert result.totals.input_tokens == 13


@pytest.mark.asyncio
async def test_loop_records_unknown_tool_as_hallucinated():
    provider = MockProvider(ModelConfig(provider="mock", model="m")).script(
        ChatResponse(
            content=None,
            tool_calls=[ToolCallRequest(id="t1", name="ghost", arguments={})],
            usage=TokenUsage(),
            stop_reason=StopReason.TOOL_USE,
        ),
        ChatResponse(
            content="oh well",
            tool_calls=[],
            usage=TokenUsage(),
            stop_reason=StopReason.END_TURN,
        ),
    )
    result = await run_agent(
        provider,
        system=None,
        user_prompt="x",
        tools={},
        budget=Budget(max_steps=5),
    )
    assert "hallucinated_tool" in result.behavior_flags
    assert result.steps[0].tool_calls[0].error.startswith("unknown tool")


@pytest.mark.asyncio
async def test_loop_respects_max_steps_budget():
    # Three tool-using responses but max_steps=2; the third turn should be gated out.
    responses = [
        ChatResponse(
            content=None,
            tool_calls=[ToolCallRequest(id=f"t{i}", name="echo", arguments={"text": "x"})],
            usage=TokenUsage(),
            stop_reason=StopReason.TOOL_USE,
        )
        for i in range(3)
    ]
    provider = MockProvider(ModelConfig(provider="mock", model="m")).script(*responses)
    tools: dict[str, Tool] = {"echo": EchoTool()}

    result = await run_agent(
        provider,
        system=None,
        user_prompt="loop forever",
        tools=tools,
        budget=Budget(max_steps=2),
    )
    assert result.status == RunStatus.BUDGET_EXCEEDED
    assert "max_steps" in (result.error or "")
    assert len(result.steps) == 2


@pytest.mark.asyncio
async def test_loop_rolls_up_cost_for_known_model():
    # claude-opus-4-7 priced at $15 in / $75 out per 1M. 1000 in + 500 out -> $0.0525.
    provider = MockProvider(ModelConfig(provider="anthropic", model="claude-opus-4-7")).script(
        ChatResponse(
            content="done",
            tool_calls=[],
            usage=TokenUsage(input_tokens=1_000, output_tokens=500),
            stop_reason=StopReason.END_TURN,
        )
    )
    result = await run_agent(
        provider,
        system=None,
        user_prompt="hi",
        tools={},
        budget=Budget(max_steps=5),
    )
    assert result.totals.cost_usd == pytest.approx(0.0525)


@pytest.mark.asyncio
async def test_loop_max_cost_budget_gates():
    # Every turn costs ~$0.0525; max_cost_usd=0.10 should fire after the second turn.
    responses = [
        ChatResponse(
            content=None,
            tool_calls=[ToolCallRequest(id=f"t{i}", name="echo", arguments={"text": "x"})],
            usage=TokenUsage(input_tokens=1_000, output_tokens=500),
            stop_reason=StopReason.TOOL_USE,
        )
        for i in range(5)
    ]
    provider = MockProvider(ModelConfig(provider="anthropic", model="claude-opus-4-7")).script(
        *responses
    )
    tools: dict[str, Tool] = {"echo": EchoTool()}
    result = await run_agent(
        provider,
        system=None,
        user_prompt="loop",
        tools=tools,
        budget=Budget(max_steps=10, max_cost_usd=0.10),
    )
    assert result.status == RunStatus.BUDGET_EXCEEDED
    assert "max_cost_usd" in (result.error or "")


@pytest.mark.asyncio
async def test_loop_records_provider_error_as_error_status():
    class ExplodingProvider(MockProvider):
        async def chat(self, messages, tools, *, max_tokens=4096, temperature=0.0):
            raise RuntimeError("provider exploded")

    provider = ExplodingProvider(ModelConfig(provider="mock", model="m"))
    result = await run_agent(
        provider,
        system=None,
        user_prompt="x",
        tools={},
        budget=Budget(max_steps=5),
    )
    assert result.status == RunStatus.ERROR
    assert "provider exploded" in (result.error or "")
