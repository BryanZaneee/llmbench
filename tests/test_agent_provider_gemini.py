"""Tests for the GeminiProvider wire-format translation.

Uses httpx.MockTransport to intercept outgoing requests so we can inspect
the serialised body and inject canned responses without touching the network.
"""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from llmbench.agent.provider import (
    ChatMessage,
    ChatResponse,
    StopReason,
    ToolCallRequest,
    ToolDefinition,
)
from llmbench.agent.providers.gemini import GeminiProvider
from llmbench.schema import ModelConfig


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_response(
    parts: list[dict[str, Any]],
    finish_reason: str = "STOP",
    usage: dict[str, Any] | None = None,
    status_code: int = 200,
) -> httpx.Response:
    body = {
        "candidates": [
            {
                "content": {"role": "model", "parts": parts},
                "finishReason": finish_reason,
            }
        ],
        "usageMetadata": usage or {"promptTokenCount": 5, "candidatesTokenCount": 3},
    }
    return httpx.Response(status_code, json=body)


def _provider(handler, *, env_key: str = "test-key") -> GeminiProvider:
    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(transport=transport)
    config = ModelConfig(provider="gemini", model="gemini-1.5-flash")
    return GeminiProvider(config, client=client)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_missing_api_key_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    config = ModelConfig(provider="gemini", model="gemini-1.5-flash")
    with pytest.raises(RuntimeError, match="GEMINI_API_KEY is not set"):
        GeminiProvider(config)


@pytest.mark.asyncio
async def test_happy_path_text_turn(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")

    def handler(request: httpx.Request) -> httpx.Response:
        return _make_response(
            [{"text": "Hello, world!"}],
            finish_reason="STOP",
            usage={"promptTokenCount": 10, "candidatesTokenCount": 4},
        )

    provider = _provider(handler)
    messages = [
        ChatMessage(role="system", content="You are helpful."),
        ChatMessage(role="user", content="Say hello."),
    ]
    resp = await provider.chat(messages, [])
    assert resp.content == "Hello, world!"
    assert resp.stop_reason == StopReason.END_TURN
    assert resp.tool_calls == []
    assert resp.usage.input_tokens == 10
    assert resp.usage.output_tokens == 4
    await provider.aclose()


@pytest.mark.asyncio
async def test_tool_call_emission(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")

    def handler(request: httpx.Request) -> httpx.Response:
        return _make_response(
            [{"functionCall": {"name": "get_weather", "args": {"city": "London"}}}],
            finish_reason="STOP",
        )

    tool = ToolDefinition(
        name="get_weather",
        description="Get weather for a city.",
        input_schema={"type": "object", "properties": {"city": {"type": "string"}}},
    )
    provider = _provider(handler)
    messages = [ChatMessage(role="user", content="What is the weather in London?")]
    resp = await provider.chat(messages, [tool])
    assert resp.stop_reason == StopReason.TOOL_USE
    assert len(resp.tool_calls) == 1
    tc = resp.tool_calls[0]
    assert tc.name == "get_weather"
    assert tc.arguments == {"city": "London"}
    assert tc.id == "gemini_call_0"
    await provider.aclose()


@pytest.mark.asyncio
async def test_round_trip_with_tool_result(monkeypatch: pytest.MonkeyPatch) -> None:
    """Outgoing body must contain a model/functionCall then user/functionResponse."""
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")

    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return _make_response([{"text": "done"}], finish_reason="STOP")

    provider = _provider(handler)
    messages = [
        ChatMessage(role="user", content="Use the tool."),
        ChatMessage(
            role="assistant",
            content=None,
            tool_calls=[ToolCallRequest(id="gemini_call_0", name="get_weather", arguments={"city": "Paris"})],
        ),
        ChatMessage(role="tool", content="Sunny, 20C", tool_call_id="gemini_call_0"),
    ]
    await provider.chat(messages, [])

    contents = captured["body"]["contents"]
    # First content: user turn
    assert contents[0]["role"] == "user"
    # Second content: model turn with functionCall
    model_turn = contents[1]
    assert model_turn["role"] == "model"
    assert "functionCall" in model_turn["parts"][0]
    assert model_turn["parts"][0]["functionCall"]["name"] == "get_weather"
    # Third content: user turn with functionResponse naming the same function
    tool_turn = contents[2]
    assert tool_turn["role"] == "user"
    fr = tool_turn["parts"][0]["functionResponse"]
    assert fr["name"] == "get_weather"
    assert fr["response"]["output"] == "Sunny, 20C"
    await provider.aclose()


@pytest.mark.asyncio
async def test_cached_tokens(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")

    def handler(request: httpx.Request) -> httpx.Response:
        return _make_response(
            [{"text": "cached"}],
            usage={"promptTokenCount": 20, "candidatesTokenCount": 5, "cachedContentTokenCount": 10},
        )

    provider = _provider(handler)
    resp = await provider.chat([ChatMessage(role="user", content="hi")], [])
    assert resp.usage.cached_input_tokens == 10
    assert resp.usage.input_tokens == 20
    await provider.aclose()


@pytest.mark.asyncio
async def test_system_instruction_joined(monkeypatch: pytest.MonkeyPatch) -> None:
    """Two system messages must be joined and placed in system_instruction.parts[0].text."""
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")

    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return _make_response([{"text": "ok"}])

    provider = _provider(handler)
    messages = [
        ChatMessage(role="system", content="Rule one."),
        ChatMessage(role="system", content="Rule two."),
        ChatMessage(role="user", content="Go."),
    ]
    await provider.chat(messages, [])
    body = captured["body"]
    assert "system_instruction" in body
    text = body["system_instruction"]["parts"][0]["text"]
    assert "Rule one." in text
    assert "Rule two." in text
    # System messages must not bleed into contents.
    for entry in body["contents"]:
        assert entry["role"] != "system"
    await provider.aclose()


@pytest.mark.asyncio
async def test_safety_finish_reason(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")

    def handler(request: httpx.Request) -> httpx.Response:
        return _make_response([{"text": ""}], finish_reason="SAFETY")

    provider = _provider(handler)
    resp = await provider.chat([ChatMessage(role="user", content="bad prompt")], [])
    assert resp.stop_reason == StopReason.REFUSED
    await provider.aclose()


@pytest.mark.asyncio
async def test_non_2xx_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, text="Bad Request")

    provider = _provider(handler)
    with pytest.raises(RuntimeError):
        await provider.chat([ChatMessage(role="user", content="hi")], [])
    await provider.aclose()
