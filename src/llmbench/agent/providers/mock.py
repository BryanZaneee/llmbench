"""Scripted ChatProvider for tests. Does not hit the network.

Constructed (or fluent-scripted via `.script(...)`) with a list of pre-baked
ChatResponses; emits them in order. The loop above drives one turn per response.
"""

from __future__ import annotations

from collections import deque

from ...schema import ModelConfig, TokenUsage
from ..provider import ChatMessage, ChatProvider, ChatResponse, StopReason, ToolDefinition


class MockProvider(ChatProvider):
    """Scripted provider for tests. Records every conversation it received per turn."""

    def __init__(self, config: ModelConfig, *, scripted: list[ChatResponse] | None = None):
        super().__init__(config)
        self._responses: deque[ChatResponse] = deque(scripted or [])
        self.received: list[list[ChatMessage]] = []

    def script(self, *responses: ChatResponse) -> "MockProvider":
        self._responses.extend(responses)
        return self

    async def chat(
        self,
        messages: list[ChatMessage],
        tools: list[ToolDefinition],
        *,
        max_tokens: int = 4096,
        temperature: float = 0.0,
    ) -> ChatResponse:
        self.received.append(list(messages))
        if not self._responses:
            return ChatResponse(
                content="(mock provider exhausted)",
                tool_calls=[],
                usage=TokenUsage(),
                stop_reason=StopReason.END_TURN,
            )
        return self._responses.popleft()
