"""Adapters are wire protocols, not vendors.

`spec.adapter` picks the protocol; `spec.provider` picks the key and base URL
out of config.PROVIDERS. That is why there is no "moonshot" or "groq" adapter:
they speak OpenAI's protocol, so they are `adapter: openai_compat`.
"""

from __future__ import annotations

from ..schema import ModelSpec
from .anthropic import AnthropicAdapter
from .base import Adapter, GenerationEvent, ImageResult, StreamedGeneration
from .flux import FluxAdapter
from .gemini import GeminiAdapter
from .openai_compat import OpenAICompatAdapter

_REGISTRY: dict[str, type[Adapter]] = {
    "anthropic": AnthropicAdapter,
    "openai_compat": OpenAICompatAdapter,
    "gemini": GeminiAdapter,
    "flux": FluxAdapter,
}


def adapter_class(spec: ModelSpec) -> type[Adapter]:
    cls = _REGISTRY.get(spec.adapter)
    if cls is None:
        raise ValueError(f"Unknown adapter: {spec.adapter!r}. Known: {sorted(_REGISTRY)}")
    return cls


def build_adapter(spec: ModelSpec) -> Adapter:
    return adapter_class(spec)(spec)


__all__ = [
    "Adapter",
    "GenerationEvent",
    "ImageResult",
    "StreamedGeneration",
    "adapter_class",
    "build_adapter",
]
