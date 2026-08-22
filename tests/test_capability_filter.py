"""A benchmark only runs against an adapter that can actually do it."""

from __future__ import annotations

import pytest

from llmbench.config import SuiteConfig
from llmbench.runner import _pair_runs
from llmbench.schema import ModelSpec

CFG = SuiteConfig(models=[], benchmarks=["throughput", "image_gen"])


def spec(**kw) -> ModelSpec:
    return ModelSpec(**{"provider": "x", "adapter": "openai_compat", "model": "m", **kw})


def test_text_only_adapter_skips_image_gen():
    # flux declares IMAGE_GEN only; its stream_generate raises.
    with pytest.warns(UserWarning, match="no text capability"):
        assert _pair_runs(spec(provider="flux", adapter="flux"), "throughput", CFG) is False


def test_image_only_adapter_runs_image_gen():
    assert _pair_runs(spec(provider="flux", adapter="flux"), "image_gen", CFG) is True


def test_anthropic_skips_image_gen():
    with pytest.warns(UserWarning, match="no image_gen capability"):
        assert _pair_runs(spec(adapter="anthropic"), "image_gen", CFG) is False


def test_openai_compat_does_both():
    assert _pair_runs(spec(), "throughput", CFG) is True
    assert _pair_runs(spec(), "image_gen", CFG) is True


def test_model_level_allowlist_still_wins():
    s = spec(benchmarks=["image_gen"])
    assert _pair_runs(s, "throughput", CFG) is False
    assert _pair_runs(s, "image_gen", CFG) is True


def test_unknown_adapter_raises_rather_than_skipping_silently():
    with pytest.raises(ValueError, match="Unknown adapter"):
        _pair_runs(spec(adapter="typo"), "throughput", CFG)
