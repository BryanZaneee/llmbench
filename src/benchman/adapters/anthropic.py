"""Claude adapter. Streams via messages.stream() and reads final usage off the final message."""

from __future__ import annotations

import time

from anthropic import AsyncAnthropic

from ..config import env
from ..schema import Capability, ModelSpec, TokenUsage
from .base import Adapter, GenerationEvent, StreamedGeneration


class AnthropicAdapter(Adapter):
    capabilities = {Capability.TEXT}

    def __init__(self, spec: ModelSpec):
        super().__init__(spec)
        self._client = AsyncAnthropic(
            api_key=env("ANTHROPIC_API_KEY"),
            base_url=spec.base_url,
        )

    async def stream_generate(
        self,
        prompt: str,
        *,
        max_tokens: int,
        temperature: float,
        top_p: float,
    ) -> StreamedGeneration:
        events: list[GenerationEvent] = []
        async with self._client.messages.stream(
            model=self.spec.model,
            max_tokens=max_tokens,
            temperature=temperature,
            top_p=top_p,
            messages=[{"role": "user", "content": prompt}],
        ) as stream:
            async for text in stream.text_stream:
                if text:
                    events.append(GenerationEvent(text=text, timestamp=time.perf_counter()))
            final = await stream.get_final_message()

        text = "".join(
            b.text for b in final.content if getattr(b, "type", None) == "text"
        )
        usage = TokenUsage(
            input_tokens=final.usage.input_tokens,
            output_tokens=final.usage.output_tokens,
            cached_input_tokens=getattr(final.usage, "cache_read_input_tokens", 0) or 0,
        )
        return StreamedGeneration(
            text=text, events=events, usage=usage, stop_reason=final.stop_reason
        )

    async def aclose(self) -> None:
        await self._client.close()
