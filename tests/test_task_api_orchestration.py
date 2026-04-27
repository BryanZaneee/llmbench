import pytest

from llmbench.agent import run_agent
from llmbench.agent.provider import ChatResponse, StopReason, ToolCallRequest
from llmbench.agent.providers.mock import MockProvider
from llmbench.schema import ModelConfig, RunStatus, TokenUsage, VerdictResult
from llmbench.tasks import get_task


def _tc(id: str, name: str, **kwargs) -> ToolCallRequest:
    return ToolCallRequest(id=id, name=name, arguments=kwargs)


def _resp(*tool_calls: ToolCallRequest, stop: StopReason = StopReason.TOOL_USE) -> ChatResponse:
    return ChatResponse(
        content=None,
        tool_calls=list(tool_calls),
        usage=TokenUsage(input_tokens=10, output_tokens=5),
        stop_reason=stop,
    )


def _end(content: str = "done") -> ChatResponse:
    return ChatResponse(
        content=content,
        tool_calls=[],
        usage=TokenUsage(input_tokens=5, output_tokens=2),
        stop_reason=StopReason.END_TURN,
    )


@pytest.mark.asyncio
async def test_check_fails_on_untouched_setup():
    task = get_task("api-orchestration")
    task.setup()
    result = task.check()
    assert result.verdict == VerdictResult.FAIL
    assert "GET" in result.detail


@pytest.mark.asyncio
async def test_check_passes_correct_sequence():
    task = get_task("api-orchestration")
    setup = task.setup()

    provider = MockProvider(ModelConfig(provider="mock", model="m")).script(
        _resp(_tc("g1", "http_get", path="/users")),
        _resp(
            _tc("p1", "http_post", path="/audit", body={"user_id": 1, "name": "Alice"}),
            _tc("p2", "http_post", path="/audit", body={"user_id": 2, "name": "Bob"}),
            _tc("p3", "http_post", path="/audit", body={"user_id": 3, "name": "Carol"}),
        ),
        _end(),
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


@pytest.mark.asyncio
async def test_check_fails_wrong_body_shape():
    task = get_task("api-orchestration")
    setup = task.setup()

    provider = MockProvider(ModelConfig(provider="mock", model="m")).script(
        _resp(_tc("g1", "http_get", path="/users")),
        _resp(
            # passes id instead of user_id -- wrong shape
            _tc("p1", "http_post", path="/audit", body={"id": 1, "name": "Alice"}),
            _tc("p2", "http_post", path="/audit", body={"user_id": 2, "name": "Bob"}),
            _tc("p3", "http_post", path="/audit", body={"user_id": 3, "name": "Carol"}),
        ),
        _end(),
    )

    await run_agent(
        provider,
        system=setup.system,
        user_prompt=setup.user_prompt,
        tools=setup.tools,
        budget=setup.budget,
    )

    verdict = task.check()
    assert verdict.verdict == VerdictResult.FAIL
    assert "keys" in verdict.detail or "user_id" in verdict.detail


@pytest.mark.asyncio
async def test_check_fails_only_two_users_posted():
    task = get_task("api-orchestration")
    setup = task.setup()

    provider = MockProvider(ModelConfig(provider="mock", model="m")).script(
        _resp(_tc("g1", "http_get", path="/users")),
        _resp(
            _tc("p1", "http_post", path="/audit", body={"user_id": 1, "name": "Alice"}),
            _tc("p2", "http_post", path="/audit", body={"user_id": 2, "name": "Bob"}),
        ),
        _end(),
    )

    await run_agent(
        provider,
        system=setup.system,
        user_prompt=setup.user_prompt,
        tools=setup.tools,
        budget=setup.budget,
    )

    verdict = task.check()
    assert verdict.verdict == VerdictResult.FAIL
    assert "3" in verdict.detail and "2" in verdict.detail
