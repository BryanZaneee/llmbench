import pytest

from llmbench.agent import run_agent
from llmbench.agent.provider import ChatResponse, StopReason, ToolCallRequest
from llmbench.agent.providers.mock import MockProvider
from llmbench.schema import ModelConfig, RunStatus, TokenUsage, VerdictResult
from llmbench.tasks import get_task


def _build_rename_script(seeded_files: dict[str, str]) -> list[ChatResponse]:
    """Mock-provider script that performs the rename via tool calls."""
    paths = sorted(seeded_files.keys())
    script: list[ChatResponse] = []

    script.append(
        ChatResponse(
            content=None,
            tool_calls=[ToolCallRequest(id="ls", name="list_dir", arguments={"prefix": ""})],
            usage=TokenUsage(input_tokens=20, output_tokens=5),
            stop_reason=StopReason.TOOL_USE,
        )
    )

    for i, path in enumerate(paths):
        script.append(
            ChatResponse(
                content=None,
                tool_calls=[ToolCallRequest(id=f"r{i}", name="read_file", arguments={"path": path})],
                usage=TokenUsage(input_tokens=10, output_tokens=3),
                stop_reason=StopReason.TOOL_USE,
            )
        )
        renamed = seeded_files[path].replace("process_data", "transform_data")
        script.append(
            ChatResponse(
                content=None,
                tool_calls=[
                    ToolCallRequest(
                        id=f"w{i}",
                        name="write_file",
                        arguments={"path": path, "content": renamed},
                    )
                ],
                usage=TokenUsage(input_tokens=10, output_tokens=3),
                stop_reason=StopReason.TOOL_USE,
            )
        )

    script.append(
        ChatResponse(
            content="renamed everywhere",
            tool_calls=[],
            usage=TokenUsage(input_tokens=10, output_tokens=3),
            stop_reason=StopReason.END_TURN,
        )
    )
    return script


@pytest.mark.asyncio
async def test_check_fails_on_untouched_state():
    task = get_task("file-refactor")
    task.setup()
    result = task.check()
    assert result.verdict == VerdictResult.FAIL
    assert "process_data" in result.detail


@pytest.mark.asyncio
async def test_check_passes_when_agent_renames_everything():
    task = get_task("file-refactor")
    setup = task.setup()
    seeded = dict(task._fs.files)
    budget = setup.budget
    # Bump budget to comfortably fit the scripted rename (one turn per file plus list_dir + done).
    budget.max_steps = 2 + 2 * len(seeded)

    provider = MockProvider(ModelConfig(provider="mock", model="m")).script(
        *_build_rename_script(seeded)
    )

    outcome = await run_agent(
        provider,
        system=setup.system,
        user_prompt=setup.user_prompt,
        tools=setup.tools,
        budget=budget,
    )

    assert outcome.status == RunStatus.SUCCESS, outcome.error
    verdict = task.check()
    assert verdict.verdict == VerdictResult.PASS, verdict.detail
