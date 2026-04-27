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


# ──────────────────────────────────────────────────────────────────────────
# Agentic-task schema (v1 engine).
#
# TraceDocument is the JSON contract between the engine and every consumer
# (TUI, Web, hosted FastAPI). One file per agent run, written to ./runs/.
# Shape and field names follow llmbench-prd.md verbatim except for
# `model_config` which is aliased: pydantic v2 reserves the attribute name
# `model_config` for class config, so the Python attribute is `target_model`
# and the JSON key stays `model_config` via Field(alias=...).
# ──────────────────────────────────────────────────────────────────────────


class RunStatus(str, Enum):
    SUCCESS = "success"
    FAILURE = "failure"
    BUDGET_EXCEEDED = "budget_exceeded"
    ERROR = "error"


class VerdictResult(str, Enum):
    PASS = "pass"
    FAIL = "fail"


class StepRole(str, Enum):
    ASSISTANT = "assistant"
    TOOL = "tool"


class ModelConfig(BaseModel):
    """The (provider, model, params) triple identifying a chat run target."""

    provider: str
    model: str
    params: dict[str, Any] = Field(default_factory=dict)


class StepTokens(BaseModel):
    input: int = 0
    output: int = 0
    cached: int = 0


class ToolCallTrace(BaseModel):
    """A tool invocation as recorded in the trace.

    Distinct from the in-flight ToolCallRequest the model emits: the trace
    records the post-execution view (input the model gave, output the tool
    returned, duration, any error).
    """

    name: str
    input: dict[str, Any] = Field(default_factory=dict)
    output: Any = None
    duration_ms: float = 0.0
    error: str | None = None


class Step(BaseModel):
    step_id: int
    role: StepRole
    content: str | None = None
    tool_calls: list[ToolCallTrace] = Field(default_factory=list)
    tokens: StepTokens = Field(default_factory=StepTokens)
    timing_ms: float = 0.0


class StepList(BaseModel):
    steps: list[Step] = Field(default_factory=list)


class Totals(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0
    cached_tokens: int = 0
    cost_usd: float = 0.0
    wall_time_ms: float = 0.0
    time_to_first_token_ms: float | None = None
    tool_call_count: int = 0


class Verdicts(BaseModel):
    final_state_check: VerdictResult
    behavior_flags: list[str] = Field(default_factory=list)


class Budget(BaseModel):
    """Stop conditions for the agent loop. First limit hit ends the run as budget_exceeded."""

    max_steps: int = 30
    max_input_tokens: int | None = None
    max_output_tokens: int | None = None
    max_wall_time_ms: int | None = None
    max_cost_usd: float | None = None


class TraceDocument(BaseModel):
    """Top-level trace per llmbench-prd.md. One file per agent run."""

    model_config = {"populate_by_name": True, "protected_namespaces": ()}

    run_id: str = Field(default_factory=_uid)
    created_at: datetime = Field(default_factory=_now)
    suite_hash: str = ""
    task_id: str
    task_version: str
    target_model: ModelConfig = Field(alias="model_config")
    status: RunStatus
    totals: Totals = Field(default_factory=Totals)
    verdicts: Verdicts | None = None
    trace: StepList = Field(default_factory=StepList)
    error: str | None = None
