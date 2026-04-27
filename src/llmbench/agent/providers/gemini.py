"""Google Gemini chat provider via raw httpx (no SDK), per llmbench-prd.md.

Translates the vendor-neutral ChatMessage shape into Gemini's contents/parts
wire format: functionCall parts for assistant tool calls, functionResponse
parts (carried on a user-role message) for tool returns. Tool-call IDs are
synthesized per-turn since Gemini's API does not return them.
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

_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"


def _stop_reason(finish_reason: str, has_tool_calls: bool) -> StopReason:
    if has_tool_calls:
        return StopReason.TOOL_USE
    if finish_reason == "STOP":
        return StopReason.END_TURN
    if finish_reason == "MAX_TOKENS":
        return StopReason.MAX_TOKENS
    if finish_reason in {"SAFETY", "RECITATION", "BLOCKLIST"}:
        return StopReason.REFUSED
    return StopReason.END_TURN


class GeminiProvider(ChatProvider):
    def __init__(self, config: ModelConfig, *, client: httpx.AsyncClient | None = None):
        super().__init__(config)
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY is not set")
        self._headers = {
            "x-goog-api-key": api_key,
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
        max_tokens = self.config.params.get("max_tokens", max_tokens)
        temperature = self.config.params.get("temperature", temperature)
        body = self._build_body(messages, tools, max_tokens=max_tokens, temperature=temperature)
        url = f"{_BASE_URL}/{self.config.model}:generateContent"
        started = time.perf_counter()
        resp = await self._client.post(url, headers=self._headers, json=body)
        latency_ms = (time.perf_counter() - started) * 1000
        if resp.status_code >= 300:
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
        # Gather system messages into a single top-level instruction block.
        system_parts = [m.content for m in messages if m.role == "system" and m.content]
        contents: list[dict[str, Any]] = []

        for msg in messages:
            if msg.role == "system":
                continue
            if msg.role == "user":
                contents.append({"role": "user", "parts": [{"text": msg.content or ""}]})
            elif msg.role == "assistant":
                if msg.tool_calls:
                    parts = [
                        {"functionCall": {"name": tc.name, "args": tc.arguments}}
                        for tc in msg.tool_calls
                    ]
                    contents.append({"role": "model", "parts": parts})
                else:
                    contents.append({"role": "model", "parts": [{"text": msg.content or ""}]})
            elif msg.role == "tool":
                # tool_call_id is the synthesized ID; use content as output.
                # The loop stores the tool name in the preceding assistant message's
                # tool_calls list, but here we only have tool_call_id which is
                # "gemini_call_{i}". We need the function name, which the loop
                # copies into ChatMessage via ToolCallRequest.name. However the
                # loop's tool message only carries tool_call_id, not the name.
                # We resolve by scanning backwards for the matching ToolCallRequest.
                name = _resolve_tool_name(msg.tool_call_id, messages)
                contents.append(
                    {
                        "role": "user",
                        "parts": [
                            {
                                "functionResponse": {
                                    "name": name,
                                    "response": {"output": msg.content or ""},
                                }
                            }
                        ],
                    }
                )

        body: dict[str, Any] = {
            "contents": contents,
            "generationConfig": {
                "maxOutputTokens": max_tokens,
                "temperature": temperature,
            },
        }
        if system_parts:
            body["system_instruction"] = {"parts": [{"text": "\n".join(system_parts)}]}
        if tools:
            body["tools"] = [
                {
                    "functionDeclarations": [
                        {
                            "name": t.name,
                            "description": t.description,
                            "parameters": t.input_schema,
                        }
                        for t in tools
                    ]
                }
            ]
        return body

    def _parse_response(self, data: dict[str, Any], *, latency_ms: float) -> ChatResponse:
        candidate = (data.get("candidates") or [{}])[0]
        content_obj = candidate.get("content", {})
        parts = content_obj.get("parts", [])
        finish_reason = candidate.get("finishReason", "STOP")

        text_parts: list[str] = []
        tool_calls: list[ToolCallRequest] = []
        for i, part in enumerate(parts):
            if "text" in part:
                text_parts.append(part["text"])
            elif "functionCall" in part:
                fc = part["functionCall"]
                tool_calls.append(
                    ToolCallRequest(
                        id=f"gemini_call_{i}",
                        name=fc["name"],
                        arguments=fc.get("args", {}),
                    )
                )

        meta = data.get("usageMetadata", {})
        token_usage = TokenUsage(
            input_tokens=int(meta.get("promptTokenCount", 0)),
            output_tokens=int(meta.get("candidatesTokenCount", 0)),
            cached_input_tokens=int(meta.get("cachedContentTokenCount", 0)),
        )
        return ChatResponse(
            content="".join(text_parts) or None,
            tool_calls=tool_calls,
            usage=token_usage,
            stop_reason=_stop_reason(finish_reason, bool(tool_calls)),
            latency_ms=latency_ms,
            raw=data,
        )


def _resolve_tool_name(tool_call_id: str | None, messages: list[ChatMessage]) -> str:
    """Scan prior assistant messages to find the ToolCallRequest matching this ID."""
    for msg in reversed(messages):
        if msg.role == "assistant":
            for tc in msg.tool_calls:
                if tc.id == tool_call_id:
                    return tc.name
    # Fallback: use the ID itself so the wire message stays structurally valid.
    return tool_call_id or "unknown"
