import pytest

from llmbench.agent import run_agent
from llmbench.agent.provider import ChatResponse, StopReason, ToolCallRequest
from llmbench.agent.providers.mock import MockProvider
from llmbench.schema import ModelConfig, RunStatus, TokenUsage, VerdictResult
from llmbench.tasks import get_task

_MOCK_CONFIG = ModelConfig(provider="mock", model="m")

_FULL_REPORT = """\
## Sales
Headcount: 18
Highlight: closed Q1 enterprise deal

## Support
Headcount: 12
Highlight: reduced p50 ticket resolution to 4h

## Engineering
Headcount: 34
Highlight: shipped agentic v1

## Summary
Total headcount: 64

Team highlights:
- closed Q1 enterprise deal
- reduced p50 ticket resolution to 4h
- shipped agentic v1
"""


def _turn(tool_name: str, arguments: dict, call_id: str) -> ChatResponse:
    return ChatResponse(
        content=None,
        tool_calls=[ToolCallRequest(id=call_id, name=tool_name, arguments=arguments)],
        usage=TokenUsage(input_tokens=10, output_tokens=5),
        stop_reason=StopReason.TOOL_USE,
    )


def _end() -> ChatResponse:
    return ChatResponse(
        content="report written",
        tool_calls=[],
        usage=TokenUsage(input_tokens=10, output_tokens=3),
        stop_reason=StopReason.END_TURN,
    )


def _full_script(report_content: str = _FULL_REPORT) -> list[ChatResponse]:
    return [
        _turn("read_file", {"path": "/config.json"}, "t1"),
        _turn("http_get", {"path": "/api/sales"}, "t2"),
        _turn("http_get", {"path": "/api/support"}, "t3"),
        _turn("http_get", {"path": "/api/eng"}, "t4"),
        _turn("write_file", {"path": "/report.md", "content": report_content}, "t5"),
        _end(),
    ]


async def _run_with_script(script: list[ChatResponse]) -> "TaskCheckResult":  # type: ignore[name-defined]  # noqa: F821
    from llmbench.tasks.base import TaskCheckResult  # local import to avoid circular at top level

    task = get_task("long-horizon")
    setup = task.setup()
    provider = MockProvider(_MOCK_CONFIG).script(*script)
    outcome = await run_agent(
        provider,
        system=setup.system,
        user_prompt=setup.user_prompt,
        tools=setup.tools,
        budget=setup.budget,
    )
    assert outcome.status == RunStatus.SUCCESS, outcome.error
    return task.check()


@pytest.mark.asyncio
async def test_check_fails_on_untouched_setup():
    task = get_task("long-horizon")
    task.setup()
    result = task.check()
    assert result.verdict == VerdictResult.FAIL
    assert "/report.md" in result.detail


@pytest.mark.asyncio
async def test_check_passes_full_flow():
    result = await _run_with_script(_full_script())
    assert result.verdict == VerdictResult.PASS, result.detail


@pytest.mark.asyncio
async def test_check_fails_missing_section():
    report_missing_eng = _FULL_REPORT.replace("## Engineering\nHeadcount: 34\nHighlight: shipped agentic v1\n\n", "")
    result = await _run_with_script(_full_script(report_missing_eng))
    assert result.verdict == VerdictResult.FAIL
    assert "Engineering" in result.detail


@pytest.mark.asyncio
async def test_check_fails_wrong_total():
    report_wrong_total = _FULL_REPORT.replace("Total headcount: 64", "Total headcount: 60")
    result = await _run_with_script(_full_script(report_wrong_total))
    assert result.verdict == VerdictResult.FAIL
    assert "64" in result.detail


@pytest.mark.asyncio
async def test_excessive_http_calls_flag():
    script: list[ChatResponse] = [
        _turn("read_file", {"path": "/config.json"}, "t1"),
        _turn("http_get", {"path": "/api/sales"}, "t2"),
        _turn("http_get", {"path": "/api/sales"}, "t3"),
        _turn("http_get", {"path": "/api/sales"}, "t4"),
        _turn("http_get", {"path": "/api/support"}, "t5"),
        _turn("http_get", {"path": "/api/support"}, "t6"),
        _turn("http_get", {"path": "/api/support"}, "t7"),
        _turn("http_get", {"path": "/api/eng"}, "t8"),
        _turn("http_get", {"path": "/api/eng"}, "t9"),
        _turn("http_get", {"path": "/api/eng"}, "t10"),
        _turn("write_file", {"path": "/report.md", "content": _FULL_REPORT}, "t11"),
        _end(),
    ]
    result = await _run_with_script(script)
    assert result.verdict == VerdictResult.PASS, result.detail
    assert "excessive_http_calls" in result.behavior_flags
