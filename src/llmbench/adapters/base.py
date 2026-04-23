"""Adapter contract. Each provider (Claude, OpenAI, Ollama, ...) subclasses Adapter.

The single required method is `stream_generate()`, which streams a completion
and returns the chunks (with timestamps) plus final token usage — everything a
benchmark needs to measure TTFT, tok/s, and costs from one call.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from ..schema import Capability, ModelSpec, TokenUsage


@dataclass
class GenerationEvent:
    """Streamed chunk with its arrival timestamp (perf_counter seconds)."""

    text: str
    timestamp: float


@dataclass
class StreamedGeneration:
    text: str
    events: list[GenerationEvent]
    usage: TokenUsage = field(default_factory=TokenUsage)
    stop_reason: str | None = None


@dataclass
class ImageResult:
    images: list[bytes]
    width: int
    height: int
    usage: TokenUsage = field(default_factory=TokenUsage)


class Adapter(ABC):
    capabilities: set[Capability] = {Capability.TEXT}

    def __init__(self, spec: ModelSpec):
        self.spec = spec

    @abstractmethod
    async def stream_generate(
        self,
        prompt: str,
        *,
        max_tokens: int,
        temperature: float,
        top_p: float,
    ) -> StreamedGeneration:
        """Stream a completion, capturing per-chunk timestamps and final usage."""

    async def generate_image(self, prompt: str, **kwargs) -> ImageResult:
        raise NotImplementedError(f"{self.spec.provider} adapter does not support image gen")

    async def aclose(self) -> None:
        pass
