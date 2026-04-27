import pytest

from llmbench.agent import run_agent
from llmbench.agent.provider import ChatResponse, StopReason, ToolCallRequest
from llmbench.agent.providers.mock import MockProvider
from llmbench.schema import ModelConfig, RunStatus, TokenUsage, VerdictResult
from llmbench.tasks import get_task

_SYNTHESIS_FULL = (
    "# Llamatech Research Report\n\n"
    "## Founding\n"
    "Llamatech was founded in 2019 by Marcus Chen in Portland, Oregon.\n\n"
    "## Products\n"
    "The company released LlamaCloud in 2021 as its flagship platform.\n\n"
    "## Challenges\n"
    "Llamatech encountered supply chain issues and faced EU regulatory scrutiny.\n\n"
    "## Recent News\n"
    "In 2024, Llamatech raised $50M in a Series B funding round.\n"
)

_SYNTHESIS_NO_FOUNDING = (
    "# Llamatech Research Report\n\n"
    "## Founding\n"
    "Llamatech was started by a small team and grew quickly.\n\n"
    "## Products\n"
    "The company released LlamaCloud in 2021 as its flagship platform.\n\n"
    "## Challenges\n"
    "Llamatech encountered supply chain issues and faced EU regulatory scrutiny.\n\n"
    "## Recent News\n"
    "In 2024, Llamatech raised $50M in a Series B funding round.\n"
)

_SYNTHESIS_TOO_SHORT = "2019 LlamaCloud supply chain Series B $50M EU 2021 2024"


def _search_turn(turn_id: str, query: str) -> ChatResponse:
    return ChatResponse(
        content=None,
        tool_calls=[ToolCallRequest(id=turn_id, name="search", arguments={"query": query})],
        usage=TokenUsage(input_tokens=10, output_tokens=3),
        stop_reason=StopReason.TOOL_USE,
    )


def _write_turn(content: str) -> ChatResponse:
    return ChatResponse(
        content=None,
        tool_calls=[
            ToolCallRequest(
                id="write1",
                name="write_file",
                arguments={"path": "/research.md", "content": content},
            )
        ],
        usage=TokenUsage(input_tokens=10, output_tokens=5),
        stop_reason=StopReason.TOOL_USE,
    )


def _end_turn() -> ChatResponse:
    return ChatResponse(
        content="done",
        tool_calls=[],
        usage=TokenUsage(input_tokens=5, output_tokens=2),
        stop_reason=StopReason.END_TURN,
    )


def _full_script(synthesis: str) -> list[ChatResponse]:
    return [
        _search_turn("s1", "Llamatech founding"),
        _search_turn("s2", "Llamatech products"),
        _search_turn("s3", "Llamatech challenges"),
        _search_turn("s4", "Llamatech recent news"),
        _write_turn(synthesis),
        _end_turn(),
    ]


@pytest.mark.asyncio
async def test_check_fails_on_untouched_setup():
    task = get_task("multi-step-research")
    task.setup()
    result = task.check()
    assert result.verdict == VerdictResult.FAIL
    assert "/research.md" in result.detail


@pytest.mark.asyncio
async def test_check_passes_with_full_synthesis():
    task = get_task("multi-step-research")
    setup = task.setup()

    provider = MockProvider(ModelConfig(provider="mock", model="m")).script(
        *_full_script(_SYNTHESIS_FULL)
    )

    outcome = await run_agent(
        provider,
        system=setup.system,
        user_prompt=setup.user_prompt,
        tools=setup.tools,
        budget=setup.budget,
    )

    assert outcome.status == RunStatus.SUCCESS, outcome.error
    verdict = task.check()
    assert verdict.verdict == VerdictResult.PASS, verdict.detail
    assert "founding" in verdict.detail
    assert "products" in verdict.detail
    assert "challenges" in verdict.detail
    assert "news" in verdict.detail


@pytest.mark.asyncio
async def test_check_fails_when_founding_facts_missing():
    task = get_task("multi-step-research")
    setup = task.setup()

    provider = MockProvider(ModelConfig(provider="mock", model="m")).script(
        *_full_script(_SYNTHESIS_NO_FOUNDING)
    )

    outcome = await run_agent(
        provider,
        system=setup.system,
        user_prompt=setup.user_prompt,
        tools=setup.tools,
        budget=setup.budget,
    )

    assert outcome.status == RunStatus.SUCCESS, outcome.error
    verdict = task.check()
    assert verdict.verdict == VerdictResult.FAIL
    assert "founding" in verdict.detail


@pytest.mark.asyncio
async def test_check_fails_when_synthesis_too_short():
    task = get_task("multi-step-research")
    task.setup()
    task.fs.write("/research.md", _SYNTHESIS_TOO_SHORT)
    verdict = task.check()
    assert verdict.verdict == VerdictResult.FAIL
    assert "too short" in verdict.detail


@pytest.mark.asyncio
async def test_unregistered_search_query_flag():
    task = get_task("multi-step-research")
    setup = task.setup()

    script = [
        _search_turn("s0", "random thing"),
        _search_turn("s1", "Llamatech founding"),
        _search_turn("s2", "Llamatech products"),
        _search_turn("s3", "Llamatech challenges"),
        _search_turn("s4", "Llamatech recent news"),
        _write_turn(_SYNTHESIS_FULL),
        _end_turn(),
    ]

    provider = MockProvider(ModelConfig(provider="mock", model="m")).script(*script)

    outcome = await run_agent(
        provider,
        system=setup.system,
        user_prompt=setup.user_prompt,
        tools=setup.tools,
        budget=setup.budget,
    )

    assert outcome.status == RunStatus.SUCCESS, outcome.error
    verdict = task.check()
    assert verdict.verdict == VerdictResult.PASS, verdict.detail
    assert "unregistered_search_query" in verdict.behavior_flags
