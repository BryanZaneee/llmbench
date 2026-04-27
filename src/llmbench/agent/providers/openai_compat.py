"""OpenAI-compatible chat provider for the agent loop.

Handles both OpenAI and any vendor that exposes the same Chat Completions
wire format (e.g. Moonshot/Kimi). Callers pass base_url and api_key_env to
target a specific vendor; the translation logic is identical for all of them.
"""

from __future__ import annotations

import json
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

_STOP_REASON_MAP = {
    "stop": StopReason.END_TURN,
    "tool_calls": StopReason.TOOL_USE,
    "length": StopReason.MAX_TOKENS,
    "content_filter": StopReason.REFUSED,
}


class OpenAICompatProvider(ChatProvider):
    """ChatProvider implementation for the OpenAI Chat Completions API and compatible vendors."""

    def __init__(
        self,
        config: ModelConfig,
        *,
        client: httpx.AsyncClient | None = None,
        base_url: str = "https://api.openai.com/v1",
        api_key_env: str = "OPENAI_API_KEY",
    ):
        super().__init__(config)
        api_key = os.environ.get(api_key_env)
        if not api_key:
            raise RuntimeError(f"{api_key_env} is not set")
        self._endpoint = f"{base_url.rstrip('/')}/chat/completions"
        self._headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
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
        resp = await self._client.post(self._endpoint, headers=self._headers, json=body)
        latency_ms = (time.perf_counter() - started) * 1000
        if resp.status_code >= 400:
            raise RuntimeError(resp.text)
        return self._parse_response(resp.json(), latency_ms=latency_ms)

    def _build_body(
        self,
        messages: list[ChatMessage],
        tools: list[ToolDefinition],
        *,
        max_tokens: int,
        temperature: float,
    ) -> dict[str, Any]:
        oai_messages: list[dict[str, Any]] = []
        for msg in messages:
            if msg.role == "system":
                oai_messages.append({"role": "system", "content": msg.content or ""})
            elif msg.role == "user":
                oai_messages.append({"role": "user", "content": msg.content or ""})
            elif msg.role == "assistant":
                entry: dict[str, Any] = {
                    "role": "assistant",
                    "content": msg.content,
                }
                if msg.tool_calls:
                    entry["tool_calls"] = [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.name,
                                "arguments": json.dumps(tc.arguments),
                            },
                        }
                        for tc in msg.tool_calls
                    ]
                oai_messages.append(entry)
            elif msg.role == "tool":
                # OpenAI requires one tool-role message per result, not bundled.
                oai_messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": msg.tool_call_id,
                        "content": msg.content or "",
                    }
                )
        body: dict[str, Any] = {
            "model": self.config.model,
            "messages": oai_messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if tools:
            body["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": t.name,
                        "description": t.description,
                        "parameters": t.input_schema,
                    },
                }
                for t in tools
            ]
            body["tool_choice"] = "auto"
        return body

    def _parse_response(self, data: dict[str, Any], *, latency_ms: float) -> ChatResponse:
        message = data["choices"][0]["message"]
        content: str = message.get("content") or ""
        tool_calls: list[ToolCallRequest] = []
        for tc in message.get("tool_calls") or []:
            tool_calls.append(
                ToolCallRequest(
                    id=tc["id"],
                    name=tc["function"]["name"],
                    arguments=json.loads(tc["function"]["arguments"]),
                )
            )
        finish_reason = data["choices"][0].get("finish_reason", "stop")
        usage_raw = data.get("usage", {})
        details = usage_raw.get("prompt_tokens_details") or {}
        token_usage = TokenUsage(
            input_tokens=int(usage_raw.get("prompt_tokens", 0)),
            output_tokens=int(usage_raw.get("completion_tokens", 0)),
            cached_input_tokens=int(details.get("cached_tokens", 0)),
        )
        return ChatResponse(
            content=content or None,
            tool_calls=tool_calls,
            usage=token_usage,
            stop_reason=_STOP_REASON_MAP.get(finish_reason, StopReason.END_TURN),
            latency_ms=latency_ms,
            raw=data,
        )
