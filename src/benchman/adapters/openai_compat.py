"""One adapter for every OpenAI-protocol endpoint: OpenAI, vLLM, Ollama, LM Studio, llama.cpp.

They all speak the same chat-completions API — only the base URL differs — so a single
class handles all of them. The `adapter` field in config picks which env var holds the URL.
"""

from __future__ import annotations

import base64
import time

import httpx
from openai import AsyncOpenAI

from ..config import env
from ..schema import Capability, ModelSpec, TokenUsage
from .base import Adapter, GenerationEvent, ImageResult, StreamedGeneration

_BASE_URL_ENV = {
    "openai": None,
    "ollama": "OLLAMA_BASE_URL",
    "vllm": "VLLM_BASE_URL",
    "lmstudio": "LMSTUDIO_BASE_URL",
}


def _resolve_base_url(spec: ModelSpec) -> str | None:
    if spec.base_url:
        return spec.base_url
    key = _BASE_URL_ENV.get(spec.adapter)
    return env(key) if key else None


def _resolve_api_key(spec: ModelSpec) -> str:
    if spec.adapter == "openai":
        return env("OPENAI_API_KEY") or "missing"
    # Local OpenAI-compatible servers usually ignore the key, but the SDK requires a value.
    return env("OPENAI_API_KEY") or "local"


class OpenAICompatAdapter(Adapter):
    """OpenAI + any OpenAI-compatible server (vLLM, Ollama, LM Studio, llama.cpp)."""

    capabilities = {Capability.TEXT, Capability.IMAGE_GEN}

    def __init__(self, spec: ModelSpec):
        super().__init__(spec)
        self._client = AsyncOpenAI(
            api_key=_resolve_api_key(spec),
            base_url=_resolve_base_url(spec),
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
        usage = TokenUsage()
        stop_reason: str | None = None
        text_parts: list[str] = []

        stream = await self._client.chat.completions.create(
            model=self.spec.model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
            temperature=temperature,
            top_p=top_p,
            stream=True,
            stream_options={"include_usage": True},
        )
        async for chunk in stream:
            if chunk.usage is not None:
                usage = TokenUsage(
                    input_tokens=chunk.usage.prompt_tokens or 0,
                    output_tokens=chunk.usage.completion_tokens or 0,
                )
            if not chunk.choices:
                continue
            choice = chunk.choices[0]
            if choice.finish_reason:
                stop_reason = choice.finish_reason
            delta_text = getattr(choice.delta, "content", None)
            if delta_text:
                events.append(GenerationEvent(text=delta_text, timestamp=time.perf_counter()))
                text_parts.append(delta_text)

        return StreamedGeneration(
            text="".join(text_parts), events=events, usage=usage, stop_reason=stop_reason
        )

    async def generate_image(
        self, prompt: str, *, size: str = "1024x1024", n: int = 1, **kwargs
    ) -> ImageResult:
        resp = await self._client.images.generate(
            model=self.spec.model,
            prompt=prompt,
            n=n,
            size=size,
        )
        images: list[bytes] = []
        for datum in resp.data:
            if getattr(datum, "b64_json", None):
                images.append(base64.b64decode(datum.b64_json))
            elif getattr(datum, "url", None):
                async with httpx.AsyncClient(timeout=60) as c:
                    r = await c.get(datum.url)
                    r.raise_for_status()
                    images.append(r.content)
        width, height = (int(x) for x in size.split("x", 1)) if "x" in size else (0, 0)
        return ImageResult(images=images, width=width, height=height)

    async def aclose(self) -> None:
        await self._client.close()
