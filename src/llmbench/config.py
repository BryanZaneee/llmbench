"""Loads the YAML suite config and reads API keys from .env."""

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
    results_dir: str = "results"
    judge: ModelSpec | None = None


def load_suite(path: str | Path) -> SuiteConfig:
    raw = yaml.safe_load(Path(path).read_text())
    return SuiteConfig.model_validate(raw)


def env(name: str, default: str | None = None) -> str | None:
    return os.environ.get(name, default)
