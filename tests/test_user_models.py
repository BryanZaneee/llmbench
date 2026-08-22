from pathlib import Path

import yaml

from llmbench.config import load_user_models, save_user_model
from llmbench.schema import ModelSpec


def test_load_returns_empty_when_file_missing(tmp_path: Path):
    target = tmp_path / "models.yaml"
    assert load_user_models(target) == []


def test_save_then_load_round_trips(tmp_path: Path):
    target = tmp_path / "models.yaml"
    spec = ModelSpec(
        provider="anthropic",
        adapter="anthropic",
        model="claude-opus-4-7",
        label="Opus",
    )
    save_user_model(spec, target)
    loaded = load_user_models(target)
    assert len(loaded) == 1
    assert loaded[0].provider == "anthropic"
    assert loaded[0].model == "claude-opus-4-7"
    assert loaded[0].label == "Opus"
    # base_url is None and shouldn't appear in the YAML so the file stays terse.
    assert "base_url" not in target.read_text()


def test_save_dedupes_by_provider_model_base_url(tmp_path: Path):
    target = tmp_path / "models.yaml"
    save_user_model(
        ModelSpec(provider="openai", adapter="openai", model="gpt-4o", label="A"),
        target,
    )
    save_user_model(
        ModelSpec(provider="openai", adapter="openai", model="gpt-4o", label="B"),
        target,
    )
    loaded = load_user_models(target)
    assert len(loaded) == 1, "second save should replace, not append"
    assert loaded[0].label == "B"


def test_save_keeps_distinct_base_urls_separate(tmp_path: Path):
    target = tmp_path / "models.yaml"
    save_user_model(
        ModelSpec(
            provider="ollama",
            adapter="ollama",
            model="llama3.2",
            base_url="http://host-a:11434/v1",
        ),
        target,
    )
    save_user_model(
        ModelSpec(
            provider="ollama",
            adapter="ollama",
            model="llama3.2",
            base_url="http://host-b:11434/v1",
        ),
        target,
    )
    loaded = load_user_models(target)
    assert len(loaded) == 2


def test_save_preserves_order(tmp_path: Path):
    target = tmp_path / "models.yaml"
    specs = [
        ModelSpec(provider="anthropic", adapter="anthropic", model="claude-opus-4-7"),
        ModelSpec(provider="openai", adapter="openai", model="gpt-4o"),
        ModelSpec(provider="gemini", adapter="gemini", model="gemini-3.1-flash"),
    ]
    for s in specs:
        save_user_model(s, target)
    loaded = load_user_models(target)
    assert [m.model for m in loaded] == [s.model for s in specs]


def test_save_creates_parent_dir(tmp_path: Path):
    target = tmp_path / "nested" / "config" / "models.yaml"
    save_user_model(
        ModelSpec(provider="openai", adapter="openai", model="gpt-4o-mini"), target
    )
    assert target.exists()


def test_load_handles_empty_file(tmp_path: Path):
    target = tmp_path / "models.yaml"
    target.write_text("")
    assert load_user_models(target) == []


def test_yaml_payload_uses_models_key(tmp_path: Path):
    target = tmp_path / "models.yaml"
    save_user_model(
        ModelSpec(provider="openai", adapter="openai", model="gpt-4o"), target
    )
    raw = yaml.safe_load(target.read_text())
    assert "models" in raw
    assert isinstance(raw["models"], list)
