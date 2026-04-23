from __future__ import annotations

from ..schema import ModelSpec
from .anthropic import AnthropicAdapter
from .base import Adapter, GenerationEvent, ImageResult, StreamedGeneration
from .openai_compat import OpenAICompatAdapter

_REGISTRY: dict[str, type[Adapter]] = {
    "anthropic": AnthropicAdapter,
    "openai": OpenAICompatAdapter,
    "openai_compat": OpenAICompatAdapter,
    "ollama": OpenAICompatAdapter,
    "vllm": OpenAICompatAdapter,
    "lmstudio": OpenAICompatAdapter,
}


def build_adapter(spec: ModelSpec) -> Adapter:
    cls = _REGISTRY.get(spec.adapter)
    if cls is None:
        raise ValueError(f"Unknown adapter: {spec.adapter!r}. Known: {sorted(_REGISTRY)}")
    return cls(spec)


__all__ = [
    "Adapter",
    "GenerationEvent",
    "ImageResult",
    "StreamedGeneration",
    "build_adapter",
]
