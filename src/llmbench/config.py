"""Loads the YAML suite config and reads API keys from .env.

Also persists per-user model choices to `~/.llmbench/models.yaml` so the TUI's
custom-run flow only offers models the user has already configured.
"""

from __future__ import annotations

import os
from pathlib import Path

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel

from .schema import ModelSpec

load_dotenv()


class SamplingParams(BaseModel):
    max_tokens: int = 512
    temperature: float = 0.0
    top_p: float = 1.0


class SuiteConfig(BaseModel):
    models: list[ModelSpec]
    benchmarks: list[str] = ["throughput"]
    prompts_file: str | None = None
    sampling: SamplingParams = SamplingParams()
    repetitions: int = 3
    concurrency: int = 1


def load_suite(path: str | Path) -> SuiteConfig:
    raw = yaml.safe_load(Path(path).read_text())
    return SuiteConfig.model_validate(raw)


def env(name: str, default: str | None = None) -> str | None:
    return os.environ.get(name, default)


# ──────────────────────────────────────────────────────────────────────────
# Per-user model config (separate from suite YAMLs in the repo)
# ──────────────────────────────────────────────────────────────────────────

USER_CONFIG_DIR = Path.home() / ".llmbench"
USER_MODELS_PATH = USER_CONFIG_DIR / "models.yaml"


def _model_key(spec: ModelSpec) -> tuple[str, str, str]:
    """Identity used for de-dup. base_url matters because the same model name
    can resolve to different endpoints (e.g. two ollama hosts)."""
    return (spec.provider, spec.model, spec.base_url or "")


def load_user_models(path: Path | None = None) -> list[ModelSpec]:
    """Read user-configured models. Returns [] if the file is missing or empty."""
    target = path or USER_MODELS_PATH
    if not target.exists():
        return []
    raw = yaml.safe_load(target.read_text()) or {}
    items = raw.get("models", [])
    return [ModelSpec.model_validate(m) for m in items]


def save_user_model(spec: ModelSpec, path: Path | None = None) -> None:
    """Append (or replace, by provider+model+base_url) a model in the user config."""
    target = path or USER_MODELS_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    existing = load_user_models(target)
    keep = [m for m in existing if _model_key(m) != _model_key(spec)]
    keep.append(spec)
    target.write_text(
        yaml.safe_dump(
            {"models": [m.model_dump(exclude_none=True) for m in keep]},
            sort_keys=False,
        )
    )
