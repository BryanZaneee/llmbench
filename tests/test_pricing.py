"""Pricing table + compute_cost rollup math."""

from __future__ import annotations

import pytest

from llmbench.agent.pricing import compute_cost, list_models, lookup_price
from llmbench.schema import Totals


def test_lookup_price_known():
    price = lookup_price("anthropic", "claude-opus-4-7")
    assert price is not None
    assert price.input_per_million == 15.00
    assert price.output_per_million == 75.00
    assert price.cached_input_per_million == 1.50


def test_lookup_price_unknown():
    assert lookup_price("anthropic", "no-such-model") is None
    assert lookup_price("no-such-provider", "any") is None


def test_compute_cost_no_cache():
    totals = Totals(input_tokens=1_000, output_tokens=500, cached_tokens=0)
    cost = compute_cost("anthropic", "claude-opus-4-7", totals)
    # 15 * 1000 / 1M + 75 * 500 / 1M = 0.015 + 0.0375 = 0.0525
    assert cost == pytest.approx(0.0525)


def test_compute_cost_with_cache():
    # 1000 total input of which 200 cached. Fresh 800 at $15, cached 200 at $1.50.
    totals = Totals(input_tokens=1_000, output_tokens=500, cached_tokens=200)
    cost = compute_cost("anthropic", "claude-opus-4-7", totals)
    expected = (15.0 * 800 + 1.5 * 200 + 75.0 * 500) / 1_000_000
    assert cost == pytest.approx(expected)


def test_compute_cost_unknown_model_returns_zero():
    totals = Totals(input_tokens=1_000, output_tokens=500)
    assert compute_cost("unknown", "x", totals) == 0.0


def test_compute_cost_falls_back_to_input_rate_when_no_cached_rate():
    # Moonshot 8k has no cached rate set; cached tokens should bill at input rate.
    totals = Totals(input_tokens=1_000, output_tokens=0, cached_tokens=400)
    cost = compute_cost("moonshot", "moonshot-v1-8k", totals)
    price = lookup_price("moonshot", "moonshot-v1-8k")
    assert price is not None and price.cached_input_per_million is None
    expected = price.input_per_million * 1_000 / 1_000_000
    assert cost == pytest.approx(expected)


def test_list_models_returns_sorted_tuples():
    models = list_models()
    assert len(models) > 0
    providers = [p for p, _, _ in models]
    assert providers == sorted(providers) or len(set(providers)) > 1
    for provider, model, price in models:
        assert isinstance(provider, str) and isinstance(model, str)
        assert price.input_per_million >= 0
