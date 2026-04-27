import json

import pytest

from llmbench.agent.provider import ChatResponse, StopReason, ToolCallRequest
from llmbench.agent.providers.mock import MockProvider
from llmbench.agent.runner import run_task
from llmbench.schema import ModelConfig, RunStatus, TokenUsage, VerdictResult


@pytest.mark.asyncio
async def test_run_task_writes_trace_and_verdict_passes(tmp_path):
    """Drive file-refactor end-to-end with a scripted MockProvider; verify trace.json shape."""
    from llmbench.tasks import get_task

    task = get_task("file-refactor")
    task.setup()
    seeded = dict(task._fs.files)
    paths = sorted(seeded.keys())

    script: list[ChatResponse] = [
        ChatResponse(
            content=None,
            tool_calls=[ToolCallRequest(id="ls", name="list_dir", arguments={"prefix": ""})],
            usage=TokenUsage(input_tokens=10, output_tokens=2),
            stop_reason=StopReason.TOOL_USE,
        )
    ]
    for i, path in enumerate(paths):
        renamed = seeded[path].replace("process_data", "transform_data")
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
                usage=TokenUsage(input_tokens=10, output_tokens=2),
                stop_reason=StopReason.TOOL_USE,
            )
        )
    script.append(
        ChatResponse(
            content="done",
            tool_calls=[],
            usage=TokenUsage(input_tokens=5, output_tokens=2),
            stop_reason=StopReason.END_TURN,
        )
    )

    provider = MockProvider(ModelConfig(provider="mock", model="scripted")).script(*script)

    trace, path = await run_task(
        "file-refactor",
        ModelConfig(provider="mock", model="scripted"),
        runs_dir=tmp_path,
        provider=provider,
    )

    assert path.exists()
    assert trace.status == RunStatus.SUCCESS
    assert trace.verdicts.final_state_check == VerdictResult.PASS

    raw = json.loads(path.read_text())
    # PRD shape: top-level keys present and using the canonical alias for model_config.
    for key in ("run_id", "created_at", "task_id", "task_version", "model_config", "status", "totals", "verdicts", "trace"):
        assert key in raw, f"missing key in serialized trace: {key}"
    assert raw["model_config"]["provider"] == "mock"
    assert raw["task_id"] == "file-refactor"
    assert raw["status"] == "success"
    assert raw["verdicts"]["final_state_check"] == "pass"
    assert isinstance(raw["trace"]["steps"], list)
    assert raw["trace"]["steps"][0]["role"] == "assistant"


@pytest.mark.asyncio
async def test_run_task_marks_failure_when_verdict_fails(tmp_path):
    """Loop completes normally but the agent never edits anything; trace.status should be 'failure'."""

    provider = MockProvider(ModelConfig(provider="mock", model="m")).script(
        ChatResponse(
            content="I am not going to do this",
            tool_calls=[],
            usage=TokenUsage(input_tokens=5, output_tokens=2),
            stop_reason=StopReason.END_TURN,
        )
    )

    trace, _ = await run_task(
        "file-refactor",
        ModelConfig(provider="mock", model="m"),
        runs_dir=tmp_path,
        provider=provider,
    )

    assert trace.status == RunStatus.FAILURE
    assert trace.verdicts.final_state_check == VerdictResult.FAIL
