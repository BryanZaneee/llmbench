"""Tests for OpenAICompatProvider using httpx.MockTransport as the seam."""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from llmbench.agent.provider import (
    ChatMessage,
    StopReason,
    ToolCallRequest,
    ToolDefinition,
)
from llmbench.agent.providers.openai_compat import OpenAICompatProvider
from llmbench.schema import ModelConfig


def _make_response(
    content: str | None = None,
    tool_calls: list[dict[str, Any]] | None = None,
    finish_reason: str = "stop",
    prompt_tokens: int = 10,
    completion_tokens: int = 5,
    cached_tokens: int = 0,
    status_code: int = 200,
) -> httpx.Response:
    message: dict[str, Any] = {"role": "assistant", "content": content}
    if tool_calls:
        message["tool_calls"] = tool_calls
    usage: dict[str, Any] = {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
    }
    if cached_tokens:
        usage["prompt_tokens_details"] = {"cached_tokens": cached_tokens}
    body = {
        "choices": [{"message": message, "finish_reason": finish_reason}],
        "usage": usage,
    }
    return httpx.Response(status_code, json=body)


def _provider(
    handler,
    base_url: str = "https://api.openai.com/v1",
    api_key_env: str = "OPENAI_API_KEY",
    monkeypatch=None,
    env_key: str = "sk-test",
) -> OpenAICompatProvider:
    if monkeypatch is not None:
        monkeypatch.setenv(api_key_env, env_key)
    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(transport=transport)
    return OpenAICompatProvider(
        ModelConfig(provider="openai", model="gpt-4o"),
        client=client,
        base_url=base_url,
        api_key_env=api_key_env,
    )


@pytest.mark.asyncio
async def test_happy_path_text_turn(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

    def handler(request: httpx.Request) -> httpx.Response:
        return _make_response(content="hi", finish_reason="stop", prompt_tokens=8, completion_tokens=2)

    provider = _provider(handler, monkeypatch=None)
    resp = await provider.chat(
        [ChatMessage(role="user", content="hello")],
        tools=[],
    )
    assert resp.content == "hi"
    assert resp.stop_reason == StopReason.END_TURN
    assert resp.tool_calls == []
    assert resp.usage.input_tokens == 8
    assert resp.usage.output_tokens == 2


@pytest.mark.asyncio
async def test_tool_call_emission(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

    tc = {
        "id": "call_abc",
        "type": "function",
        "function": {"name": "get_weather", "arguments": '{"city": "London"}'},
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return _make_response(tool_calls=[tc], finish_reason="tool_calls")

    provider = _provider(handler, monkeypatch=None)
    tool_def = ToolDefinition(
        name="get_weather",
        description="Get weather",
        input_schema={"type": "object", "properties": {"city": {"type": "string"}}},
    )
    resp = await provider.chat(
        [ChatMessage(role="user", content="What is the weather in London?")],
        tools=[tool_def],
    )
    assert resp.stop_reason == StopReason.TOOL_USE
    assert len(resp.tool_calls) == 1
    tc_result = resp.tool_calls[0]
    assert tc_result.id == "call_abc"
    assert tc_result.name == "get_weather"
    assert tc_result.arguments == {"city": "London"}


@pytest.mark.asyncio
async def test_round_trip_with_tool_result(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        captured["messages"] = body["messages"]
        return _make_response(content="done", finish_reason="stop")

    provider = _provider(handler, monkeypatch=None)
    messages = [
        ChatMessage(role="user", content="do something"),
        ChatMessage(
            role="assistant",
            content=None,
            tool_calls=[ToolCallRequest(id="call_xyz", name="my_tool", arguments={"x": 1})],
        ),
        ChatMessage(role="tool", tool_call_id="call_xyz", content="tool output"),
    ]
    await provider.chat(messages, tools=[])

    sent = captured["messages"]
    tool_msg = next(m for m in sent if m.get("role") == "tool")
    assert tool_msg["tool_call_id"] == "call_xyz"
    assert tool_msg["content"] == "tool output"


@pytest.mark.asyncio
async def test_cached_tokens(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

    def handler(request: httpx.Request) -> httpx.Response:
        return _make_response(
            content="cached",
            finish_reason="stop",
            prompt_tokens=20,
            completion_tokens=4,
            cached_tokens=10,
        )

    provider = _provider(handler, monkeypatch=None)
    resp = await provider.chat([ChatMessage(role="user", content="hi")], tools=[])
    assert resp.usage.cached_input_tokens == 10
    assert resp.usage.input_tokens == 20
    assert resp.usage.output_tokens == 4


def test_missing_api_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY is not set"):
        OpenAICompatProvider(ModelConfig(provider="openai", model="gpt-4o"))


@pytest.mark.asyncio
async def test_custom_base_url_and_env_name(monkeypatch):
    monkeypatch.setenv("MOONSHOT_API_KEY", "ms-test")

    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        return _make_response(content="kimi reply", finish_reason="stop")

    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(transport=transport)
    provider = OpenAICompatProvider(
        ModelConfig(provider="moonshot", model="moonshot-v1-8k"),
        client=client,
        base_url="https://api.moonshot.ai/v1",
        api_key_env="MOONSHOT_API_KEY",
    )
    await provider.chat([ChatMessage(role="user", content="hi")], tools=[])
    assert "api.moonshot.ai" in captured["url"]
    assert captured["url"].endswith("/chat/completions")


@pytest.mark.asyncio
async def test_non_2xx_raises_runtime_error(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, text="Bad Request")

    provider = _provider(handler, monkeypatch=None)
    with pytest.raises(RuntimeError, match="Bad Request"):
        await provider.chat([ChatMessage(role="user", content="hi")], tools=[])
