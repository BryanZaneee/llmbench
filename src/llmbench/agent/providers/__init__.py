"""Concrete ChatProvider implementations.

`mock` is for tests. `anthropic` reaches the real API via httpx (no SDK).
Future providers (openai, gemini, moonshot) plug in here under the same
ChatProvider contract.
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
    raise ValueError(f"unknown provider: {config.provider}")
