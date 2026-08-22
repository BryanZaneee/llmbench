"""One config file for keys and models; env vars are the fallback."""

from __future__ import annotations

import pytest

from llmbench.config import (
    PROVIDERS,
    api_key,
    base_url,
    config_models,
    load_suite,
    render_template,
    require_key,
)


@pytest.fixture
def cfg(tmp_path):
    def write(text: str):
        p = tmp_path / "config.yaml"
        p.write_text(text)
        return p
    return write


def test_config_file_beats_env(cfg, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "from-env")
    path = cfg('api_keys:\n  openai: "from-file"\n')
    assert api_key("openai", path=path) == "from-file"


def test_env_used_when_file_has_no_entry(cfg, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "from-env")
    assert api_key("openai", path=cfg("api_keys:\n  anthropic: x\n")) == "from-env"


def test_blank_file_entry_falls_through_to_env(cfg, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "from-env")
    assert api_key("openai", path=cfg('api_keys:\n  openai: ""\n')) == "from-env"


def test_alternate_env_spelling_is_accepted(cfg, monkeypatch):
    # Together's own docs say TOGETHER_API_KEY; LiteLLM says TOGETHERAI_API_KEY.
    monkeypatch.delenv("TOGETHER_API_KEY", raising=False)
    monkeypatch.setenv("TOGETHERAI_API_KEY", "alt")
    assert api_key("together", path=cfg("api_keys:\n")) == "alt"


def test_falls_back_from_free_text_provider_to_adapter(cfg, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
    # `provider: claude` is not in PROVIDERS, but `adapter: anthropic` is.
    assert api_key("claude", "anthropic", path=cfg("api_keys:\n")) == "k"


def test_unknown_provider_resolves_to_none(cfg):
    assert api_key("nope", path=cfg("api_keys:\n")) is None


def test_require_key_names_the_config_path_and_env_var(cfg, monkeypatch):
    monkeypatch.delenv("BFL_API_KEY", raising=False)
    monkeypatch.setattr("llmbench.config.CONFIG_PATH", cfg("api_keys:\n"))
    with pytest.raises(RuntimeError, match=r"api_keys\.flux.*BFL_API_KEY"):
        require_key("flux")


def test_base_url_prefers_first_known_name():
    assert base_url("moonshot") == "https://api.moonshot.ai/v1"
    assert base_url("unknown", "ollama") == "http://localhost:11434/v1"
    assert base_url("anthropic") is None  # adapter knows its own endpoint


def test_models_load_from_config(cfg):
    path = cfg("models:\n  - { provider: ollama, adapter: openai_compat, model: llama3.2 }\n")
    specs = config_models(path)
    assert [s.model for s in specs] == ["llama3.2"]


def test_suite_without_models_falls_back_to_config(cfg, tmp_path):
    path = cfg("models:\n  - { provider: openai, adapter: openai_compat, model: gpt-4o-mini }\n")
    suite = tmp_path / "s.yaml"
    suite.write_text("benchmarks: [throughput]\n")
    assert [m.model for m in load_suite(suite, config_path=path).models] == ["gpt-4o-mini"]


def test_suite_models_win_over_config(cfg, tmp_path):
    path = cfg("models:\n  - { provider: openai, adapter: openai_compat, model: gpt-4o-mini }\n")
    suite = tmp_path / "s.yaml"
    suite.write_text("models:\n  - { provider: flux, adapter: flux, model: flux-2-klein-4b }\n")
    assert [m.model for m in load_suite(suite, config_path=path).models] == ["flux-2-klein-4b"]


def test_template_is_valid_yaml_and_covers_every_keyed_provider(cfg):
    text = render_template()
    load_suite(config_path=cfg(text))  # parses and validates
    for name, entry in PROVIDERS.items():
        if entry.env:
            assert f"# {name}: " in text, f"{name} missing from template"
            assert f"${entry.env[0]}" in text
