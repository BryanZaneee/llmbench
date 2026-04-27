"""Per-model token pricing for cost rollup.

The PRD called for `pricing.yaml`. We use a Python dict instead so editing
prices is a one-line change with type checking, and so adding a model does
not require touching a separate config file. A YAML overlay can land later
without breaking the lookup interface.

Rates are USD per million tokens. Verify against the provider's published
pricing before publishing benchmark numbers; rates drift quarterly.

`cached_input_per_million=None` means the provider does not differentiate
cached input pricing, so cached tokens are billed at the full input rate.
"""

from __future__ import annotations

from typing import NamedTuple

from ..schema import Totals


class Price(NamedTuple):
    """USD per 1M tokens, broken out by direction and cache state."""

    input_per_million: float
    output_per_million: float
    cached_input_per_million: float | None = None


# Source: provider pricing pages as of 2026-04-27. Update with care.
_PRICING: dict[tuple[str, str], Price] = {
    # Anthropic
    ("anthropic", "claude-opus-4-7"): Price(15.00, 75.00, 1.50),
    ("anthropic", "claude-sonnet-4-6"): Price(3.00, 15.00, 0.30),
    ("anthropic", "claude-haiku-4-5-20251001"): Price(0.80, 4.00, 0.08),
    # OpenAI
    ("openai", "gpt-5"): Price(1.25, 10.00, 0.125),
    ("openai", "gpt-4o"): Price(2.50, 10.00, 1.25),
    ("openai", "gpt-4o-mini"): Price(0.15, 0.60, 0.075),
    # Gemini
    ("gemini", "gemini-2.5-pro"): Price(1.25, 10.00, 0.31),
    ("gemini", "gemini-2.5-flash"): Price(0.30, 2.50, 0.075),
    # Moonshot
    ("moonshot", "kimi-k2-0905-preview"): Price(0.60, 2.50, 0.15),
    ("moonshot", "moonshot-v1-128k"): Price(2.00, 5.00),
    ("moonshot", "moonshot-v1-32k"): Price(1.00, 3.00),
    ("moonshot", "moonshot-v1-8k"): Price(0.20, 2.00),
}


def lookup_price(provider: str, model: str) -> Price | None:
    """Return the Price for a (provider, model) or None if unknown."""
    return _PRICING.get((provider, model))


def compute_cost(provider: str, model: str, totals: Totals) -> float:
    """Compute total USD for the run from the running token totals.

    Idempotent: takes a snapshot of totals and returns a fresh number, so the
    loop can call it after every turn without accumulator drift.
    """
    price = lookup_price(provider, model)
    if price is None:
        return 0.0
    cached_rate = (
        price.cached_input_per_million
        if price.cached_input_per_million is not None
        else price.input_per_million
    )
    fresh_input = max(0, totals.input_tokens - totals.cached_tokens)
    return (
        price.input_per_million * fresh_input / 1_000_000
        + cached_rate * totals.cached_tokens / 1_000_000
        + price.output_per_million * totals.output_tokens / 1_000_000
    )


def list_models() -> list[tuple[str, str, Price]]:
    """Return (provider, model, Price) for every model with a registered price."""
    return [(p, m, price) for (p, m), price in sorted(_PRICING.items())]
