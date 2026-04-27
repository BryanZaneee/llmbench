"""Concrete ChatProvider implementations.

`mock` is for tests. The vendor providers reach their respective APIs via
httpx (no SDK). `openai` and `moonshot` share the OpenAI-compatible
implementation, parameterized by base_url and api_key_env.
"""

from __future__ import annotations

from ...schema import ModelConfig
from ..provider import ChatProvider


def build_provider(config: ModelConfig) -> ChatProvider:
    """Construct a provider for a ModelConfig.

    Lazy imports keep optional surface off the hot path: a unit test using
    only the mock provider does not pay the import cost of httpx-backed
    vendor providers.
    """

    if config.provider == "mock":
        from .mock import MockProvider

        return MockProvider(config)
    if config.provider == "anthropic":
        from .anthropic import AnthropicProvider

        return AnthropicProvider(config)
    if config.provider == "openai":
        from .openai_compat import OpenAICompatProvider

        return OpenAICompatProvider(config)
    if config.provider == "moonshot":
        from .openai_compat import OpenAICompatProvider

        return OpenAICompatProvider(
            config,
            base_url="https://api.moonshot.ai/v1",
            api_key_env="MOONSHOT_API_KEY",
        )
    if config.provider == "gemini":
        from .gemini import GeminiProvider

        return GeminiProvider(config)
    raise ValueError(f"unknown provider: {config.provider}")
