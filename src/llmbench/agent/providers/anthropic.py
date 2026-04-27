"""Anthropic chat provider via raw httpx (no SDK), per llmbench-prd.md.

Translates the vendor-neutral ChatMessage shape into Anthropic's content-block
form: `tool_use` blocks for assistant tool calls, `tool_result` blocks (carried
on a synthetic user-role message) for tool returns.
"""

from __future__ import annotations

import os
import time
from typing import Any

import httpx

from ...schema import ModelConfig, TokenUsage
from ..provider import (
    ChatMessage,
    ChatProvider,
    ChatResponse,
    StopReason,
    ToolCallRequest,
    ToolDefinition,
)

_ENDPOINT = "https://api.anthropic.com/v1/messages"
_API_VERSION = "2023-06-01"

_STOP_REASON_MAP = {
    "end_turn": StopReason.END_TURN,
    "tool_use": StopReason.TOOL_USE,
    "max_tokens": StopReason.MAX_TOKENS,
    "stop_sequence": StopReason.END_TURN,
    "refusal": StopReason.REFUSED,
}


class AnthropicProvider(ChatProvider):
    def __init__(self, config: ModelConfig, *, client: httpx.AsyncClient | None = None):
        super().__init__(config)
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is not set")
        self._headers = {
            "x-api-key": api_key,
            "anthropic-version": _API_VERSION,
            "content-type": "application/json",
        }
        self._client = client or httpx.AsyncClient(timeout=httpx.Timeout(120.0))
        self._owns_client = client is None

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def chat(
        self,
        messages: list[ChatMessage],
        tools: list[ToolDefinition],
        *,
        max_tokens: int = 4096,
        temperature: float = 0.0,
    ) -> ChatResponse:
        body = self._build_body(messages, tools, max_tokens=max_tokens, temperature=temperature)
        started = time.perf_counter()
        resp = await self._client.post(_ENDPOINT, headers=self._headers, json=body)
        latency_ms = (time.perf_counter() - started) * 1000
        resp.raise_for_status()
        return self._parse_response(resp.json(), latency_ms=latency_ms)

    def _build_body(
        self,
        messages: list[ChatMessage],
        tools: list[ToolDefinition],
        *,
        max_tokens: int,
        temperature: float,
    ) -> dict[str, Any]:
        system_text = "\n\n".join(m.content or "" for m in messages if m.role == "system" and m.content)
        anthropic_messages: list[dict[str, Any]] = []
        for msg in messages:
            if msg.role == "system":
                continue
            if msg.role == "user":
                anthropic_messages.append({"role": "user", "content": msg.content or ""})
            elif msg.role == "assistant":
                blocks: list[dict[str, Any]] = []
                if msg.content:
                    blocks.append({"type": "text", "text": msg.content})
                for tc in msg.tool_calls:
                    blocks.append(
                        {
                            "type": "tool_use",
                            "id": tc.id,
                            "name": tc.name,
                            "input": tc.arguments,
                        }
                    )
                anthropic_messages.append({"role": "assistant", "content": blocks})
            elif msg.role == "tool":
                anthropic_messages.append(
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": msg.tool_call_id,
                                "content": msg.content or "",
                            }
                        ],
                    }
                )
        body: dict[str, Any] = {
            "model": self.config.model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": anthropic_messages,
        }
        if system_text:
            body["system"] = system_text
        if tools:
            body["tools"] = [
                {"name": t.name, "description": t.description, "input_schema": t.input_schema}
                for t in tools
            ]
        return body

    def _parse_response(self, data: dict[str, Any], *, latency_ms: float) -> ChatResponse:
        text_parts: list[str] = []
        tool_calls: list[ToolCallRequest] = []
        for block in data.get("content", []):
            block_type = block.get("type")
            if block_type == "text":
                text_parts.append(block.get("text", ""))
            elif block_type == "tool_use":
                tool_calls.append(
                    ToolCallRequest(
                        id=block["id"],
                        name=block["name"],
                        arguments=block.get("input", {}),
                    )
                )
        usage = data.get("usage", {})
        token_usage = TokenUsage(
            input_tokens=int(usage.get("input_tokens", 0)),
            output_tokens=int(usage.get("output_tokens", 0)),
            cached_input_tokens=int(usage.get("cache_read_input_tokens", 0)),
        )
        return ChatResponse(
            content="".join(text_parts) or None,
            tool_calls=tool_calls,
            usage=token_usage,
            stop_reason=_STOP_REASON_MAP.get(data.get("stop_reason"), StopReason.OTHER),
            latency_ms=latency_ms,
            raw=data,
        )
