"""ChatProvider contract: vendor-neutral chat-with-tools surface for the agent loop.

Each concrete provider (Anthropic, OpenAI, Gemini, Moonshot) translates this
shape to and from its own wire protocol. The loop never branches on provider
name above the adapter layer.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from ..schema import ModelConfig, TokenUsage


class StopReason(str, Enum):
    END_TURN = "end_turn"
    TOOL_USE = "tool_use"
    MAX_TOKENS = "max_tokens"
    REFUSED = "refused"
    OTHER = "other"


@dataclass
class ToolCallRequest:
    """A tool invocation requested by the model on a single turn."""

    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class ChatMessage:
    """One message in the rolling conversation passed to the provider.

    role:
      - "system"     : initial instructions
      - "user"       : task statement / human input
      - "assistant"  : model output (may carry tool_calls)
      - "tool"       : a tool's response, paired to a prior tool_call by tool_call_id
    """

    role: str
    content: str | None = None
    tool_calls: list[ToolCallRequest] = field(default_factory=list)
    tool_call_id: str | None = None


@dataclass
class ToolDefinition:
    """JSON-schema-shaped tool definition surfaced to the model."""

    name: str
    description: str
    input_schema: dict[str, Any]


@dataclass
class ChatResponse:
    content: str | None
    tool_calls: list[ToolCallRequest]
    usage: TokenUsage
    stop_reason: StopReason
    latency_ms: float = 0.0
    raw: dict[str, Any] | None = None


class ChatProvider(ABC):
    """Provider contract used by the agent loop. One implementation per vendor."""

    def __init__(self, config: ModelConfig):
        self.config = config

    @abstractmethod
    async def chat(
        self,
        messages: list[ChatMessage],
        tools: list[ToolDefinition],
        *,
        max_tokens: int = 4096,
        temperature: float = 0.0,
    ) -> ChatResponse:
        """Send one turn to the provider and return the parsed response."""

    async def aclose(self) -> None:
        pass
