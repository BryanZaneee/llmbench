"""One config file for API keys and models, plus the suite loader.

`~/.llmbench/config.yaml` holds an `api_keys:` block and a `models:` list. It
is itself a valid suite config, so `llmbench run` with no argument runs it
directly. Environment variables remain a fallback for every key, which is how
CI supplies them.

PROVIDERS is the single place a provider is described. Adding one is a row
here plus `adapter: openai_compat` on the model.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import NamedTuple

import yaml
from pydantic import BaseModel, Field

from .schema import ModelSpec


class Provider(NamedTuple):
    env: tuple[str, ...]        # accepted env var names, provider's own first
    base_url: str | None = None  # None means the adapter knows its own endpoint


# Every entry is reachable through an adapter that exists today. Names and
# base URLs are taken from each provider's own docs; where the ecosystem
# disagrees (LiteLLM spells some differently) both spellings are accepted.
PROVIDERS: dict[str, Provider] = {
    # Native protocols
    "anthropic":   Provider(("ANTHROPIC_API_KEY",)),
    "gemini":      Provider(("GEMINI_API_KEY", "GOOGLE_API_KEY")),
    "flux":        Provider(("BFL_API_KEY",)),
    # OpenAI protocol, hosted
    "openai":      Provider(("OPENAI_API_KEY",), "https://api.openai.com/v1"),
    "moonshot":    Provider(("MOONSHOT_API_KEY",), "https://api.moonshot.ai/v1"),
    "deepseek":    Provider(("DEEPSEEK_API_KEY",), "https://api.deepseek.com/v1"),
    "xai":         Provider(("XAI_API_KEY",), "https://api.x.ai/v1"),
    "groq":        Provider(("GROQ_API_KEY",), "https://api.groq.com/openai/v1"),
    "mistral":     Provider(("MISTRAL_API_KEY",), "https://api.mistral.ai/v1"),
    "together":    Provider(("TOGETHER_API_KEY", "TOGETHERAI_API_KEY"),
                            "https://api.together.ai/v1"),
    "fireworks":   Provider(("FIREWORKS_API_KEY", "FIREWORKS_AI_API_KEY"),
                            "https://api.fireworks.ai/inference/v1"),
    "openrouter":  Provider(("OPENROUTER_API_KEY",), "https://openrouter.ai/api/v1"),
    "perplexity":  Provider(("PERPLEXITY_API_KEY", "PERPLEXITYAI_API_KEY"),
                            "https://api.perplexity.ai"),
    "cerebras":    Provider(("CEREBRAS_API_KEY",), "https://api.cerebras.ai/v1"),
    "qwen":        Provider(("DASHSCOPE_API_KEY",),
                            "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"),
    "nvidia":      Provider(("NVIDIA_NIM_API_KEY", "NVIDIA_API_KEY"),
                            "https://integrate.api.nvidia.com/v1"),
    "nebius":      Provider(("NEBIUS_API_KEY",), "https://api.studio.nebius.ai/v1"),
    "deepinfra":   Provider(("DEEPINFRA_API_KEY",), "https://api.deepinfra.com/v1/openai"),
    "sambanova":   Provider(("SAMBANOVA_API_KEY",), "https://api.sambanova.ai/v1"),
    # Local servers, no key
    "ollama":      Provider((), "http://localhost:11434/v1"),
    "vllm":        Provider((), "http://localhost:8000/v1"),
    "lmstudio":    Provider((), "http://localhost:1234/v1"),
    "llamacpp":    Provider((), "http://localhost:8080/v1"),
    # Not a model provider; raises the leaderboard rate limit
    "huggingface": Provider(("HF_TOKEN", "HUGGING_FACE_HUB_TOKEN")),
}


CONFIG_DIR = Path.home() / ".llmbench"
CONFIG_PATH = CONFIG_DIR / "config.yaml"


class SamplingParams(BaseModel):
    max_tokens: int = 512
    temperature: float = 0.0
    top_p: float = 1.0


class SuiteConfig(BaseModel):
    models: list[ModelSpec] = Field(default_factory=list)
    benchmarks: list[str] = ["throughput"]
    prompts_file: str | None = None
    sampling: SamplingParams = SamplingParams()
    repetitions: int = 3
    concurrency: int = 1


def load_config(path: Path | None = None) -> dict:
    """Read the user config. Returns {} when it does not exist."""
    target = path or CONFIG_PATH
    if not target.exists():
        return {}
    return yaml.safe_load(target.read_text()) or {}


def load_suite(path: str | Path | None = None, *, config_path: Path | None = None) -> SuiteConfig:
    """Load a suite YAML, or the user config when no path is given.

    Both shapes validate as SuiteConfig; the user config just carries an extra
    api_keys block, which pydantic ignores. A suite that omits `models:` falls
    back to the ones configured in the user config.
    """
    raw = yaml.safe_load(Path(path).read_text()) if path else load_config(config_path)
    # A key left blank in YAML parses as None; treat that as "not set" so an
    # empty `models:` line in the starter config does not fail validation.
    clean = {k: v for k, v in (raw or {}).items() if v is not None}
    cfg = SuiteConfig.model_validate(clean)
    if not cfg.models:
        cfg.models = config_models(config_path)
    return cfg


def config_models(path: Path | None = None) -> list[ModelSpec]:
    return [ModelSpec.model_validate(m) for m in (load_config(path).get("models") or [])]


def api_key(*names: str, path: Path | None = None) -> str | None:
    """Resolve an API key. Config file wins, environment is the fallback.

    Names are tried in order, so an adapter passes (provider, adapter) and
    still finds a key when `provider` is free text like "claude".
    """
    configured = load_config(path).get("api_keys") or {}
    for name in names:
        value = configured.get(name)
        if value and str(value).strip():
            return str(value).strip()
    for name in names:
        for env_name in PROVIDERS.get(name, Provider(())).env:
            value = os.environ.get(env_name)
            if value:
                return value
    return None


def require_key(*names: str) -> str:
    """api_key(), but fail loudly and say exactly where to put the key."""
    key = api_key(*names)
    if key:
        return key
    envs = " or ".join(f"${e}" for e in PROVIDERS.get(names[0], Provider(())).env)
    raise RuntimeError(
        f"No API key for {names[0]!r}. Set `api_keys.{names[0]}` in {CONFIG_PATH} "
        f"(run `llmbench config --init`)" + (f", or export {envs}." if envs else ".")
    )


def base_url(*names: str) -> str | None:
    """Default endpoint for the first name that names a known provider."""
    for name in names:
        entry = PROVIDERS.get(name)
        if entry and entry.base_url:
            return entry.base_url
    return None


def render_template() -> str:
    """Build the starter config from PROVIDERS, so the two cannot drift."""
    lines = [
        "# llmbench config. Keys here win over environment variables.",
        "# Uncomment a provider and paste its key; leave the rest alone.",
        "",
        "api_keys:",
    ]
    for name, entry in PROVIDERS.items():
        if not entry.env:
            continue  # local servers take no key
        lines.append(f"  # {name}: \"\"{' ' * max(1, 14 - len(name))}# ${entry.env[0]}")
    lines += [
        "",
        "# Models available to `llmbench run` when no suite file is given.",
        "# adapter is the wire protocol: anthropic | openai_compat | gemini | flux",
        "models:",
        "  # - { provider: openai, adapter: openai_compat, model: gpt-4o-mini }",
        "  # - { provider: moonshot, adapter: openai_compat, model: kimi-k2.5 }",
        "  # - { provider: ollama, adapter: openai_compat, model: llama3.2 }",
        "",
        "benchmarks: [throughput]",
        "repetitions: 3",
        "concurrency: 2",
        "",
    ]
    return "\n".join(lines)
