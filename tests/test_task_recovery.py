import pytest

from llmbench.agent import run_agent
from llmbench.agent.provider import ChatResponse, StopReason, ToolCallRequest
from llmbench.agent.providers.mock import MockProvider
from llmbench.schema import ModelConfig, RunStatus, TokenUsage, VerdictResult
from llmbench.tasks import get_task

_MODEL = ModelConfig(provider="mock", model="m")

_INSERT_SQL = "INSERT INTO audit (action, user_id) VALUES (?, ?)"
_INSERT_PARAMS_OK = ["login", 42]
_INSERT_PARAMS_WRONG = ["logout", 42]


def _tool_call(call_id: str, sql: str, params: list) -> ChatResponse:
    return ChatResponse(
        content=None,
        tool_calls=[
            ToolCallRequest(
                id=call_id,
                name="commit_transaction",
                arguments={"sql": sql, "params": params},
            )
        ],
        usage=TokenUsage(input_tokens=10, output_tokens=3),
        stop_reason=StopReason.TOOL_USE,
    )


def _end_turn(text: str = "committed") -> ChatResponse:
    return ChatResponse(
        content=text,
        tool_calls=[],
        usage=TokenUsage(input_tokens=5, output_tokens=2),
        stop_reason=StopReason.END_TURN,
    )


@pytest.mark.asyncio
async def test_check_fails_on_untouched_setup():
    task = get_task("recovery")
    task.setup()
    result = task.check()
    assert result.verdict == VerdictResult.FAIL
    assert "did not commit" in result.detail


@pytest.mark.asyncio
async def test_check_passes_on_fail_then_retry():
    """Model calls commit_transaction twice (first fails, second succeeds); verdict PASS."""
    task = get_task("recovery")
    setup = task.setup()

    provider = MockProvider(_MODEL).script(
        _tool_call("c1", _INSERT_SQL, _INSERT_PARAMS_OK),
        _tool_call("c2", _INSERT_SQL, _INSERT_PARAMS_OK),
        _end_turn(),
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
    assert "recovered_from_transient_failure" in verdict.behavior_flags


@pytest.mark.asyncio
async def test_check_fails_when_model_gives_up():
    """Model calls commit_transaction once (fails) then gives up without retrying."""
    task = get_task("recovery")
    setup = task.setup()

    provider = MockProvider(_MODEL).script(
        _tool_call("c1", _INSERT_SQL, _INSERT_PARAMS_OK),
        _end_turn("giving up"),
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
    assert "recovered_from_transient_failure" not in verdict.behavior_flags


@pytest.mark.asyncio
async def test_check_fails_on_wrong_values():
    """Model retries but uses wrong action value; verdict FAIL with detail."""
    task = get_task("recovery")
    setup = task.setup()

    provider = MockProvider(_MODEL).script(
        _tool_call("c1", _INSERT_SQL, _INSERT_PARAMS_OK),   # fails (injector fires)
        _tool_call("c2", _INSERT_SQL, _INSERT_PARAMS_WRONG),  # succeeds but wrong
        _end_turn(),
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
    assert "logout" in verdict.detail


@pytest.mark.asyncio
async def test_check_fails_on_extra_rows():
    """Model retries successfully then calls commit_transaction a third time; verdict FAIL."""
    task = get_task("recovery")
    setup = task.setup()

    provider = MockProvider(_MODEL).script(
        _tool_call("c1", _INSERT_SQL, _INSERT_PARAMS_OK),  # fails (injector)
        _tool_call("c2", _INSERT_SQL, _INSERT_PARAMS_OK),  # succeeds
        _tool_call("c3", _INSERT_SQL, _INSERT_PARAMS_OK),  # extra row
        _end_turn(),
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
    assert "extra rows" in verdict.detail
