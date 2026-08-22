"""Data shapes for everything that crosses a boundary (config, DB, JSONL, CLI output).

Pydantic models validate incoming data and serialize cleanly to JSON.
Plain dataclasses are used for in-process values that never leave the program.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _uid() -> str:
    return uuid4().hex


class Capability(str, Enum):
    TEXT = "text"
    IMAGE_GEN = "image_gen"


class ModelSpec(BaseModel):
    """Uniquely identifies a model under test."""

    provider: str
    model: str
    adapter: str
    base_url: str | None = None
    label: str | None = None
    benchmarks: list[str] | None = None

    @property
    def display(self) -> str:
        return self.label or f"{self.provider}/{self.model}"

    def slug(self) -> str:
        return f"{self.provider}__{self.model}".replace("/", "_").replace(":", "_")


class Prompt(BaseModel):
    """A single test case. `expected` and `rubric` are used by quality benchmarks."""

    id: str
    prompt: str
    expected: str | None = None
    check: str = "contains"  # exact | contains | regex
    rubric: str | None = None


class TokenUsage(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0
    cached_input_tokens: int = 0

    @property
    def total(self) -> int:
        return self.input_tokens + self.output_tokens


class ThroughputMetrics(BaseModel):
    ttft_ms: float | None = None
    total_latency_ms: float
    output_tokens: int
    tokens_per_second: float | None = None
    inter_token_latency_ms: float | None = None


class BenchmarkResult(BaseModel):
    run_id: str = Field(default_factory=_uid)
    benchmark: str
    model: ModelSpec
    started_at: datetime = Field(default_factory=_now)
    duration_ms: float
    success: bool
    error: str | None = None
    prompt_id: str | None = None
    usage: TokenUsage = Field(default_factory=TokenUsage)
    throughput: ThroughputMetrics | None = None
    score: float | None = None
    score_reasoning: str | None = None
    image_paths: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    sample_output: str | None = None


class RunManifest(BaseModel):
    """Versioning + provenance for a batch of results."""

    run_id: str = Field(default_factory=_uid)
    created_at: datetime = Field(default_factory=_now)
    suite_version: str
    models: list[ModelSpec]
    benchmarks: list[str]
    prompts: list[Prompt] = Field(default_factory=list)
