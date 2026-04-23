"""LLM-as-judge quality benchmark.

For each prompt:
  1. Ask the model under test to respond.
  2. Ask the judge model to score the response 1-10 with a short reason.

The judge model is configured via `judge:` in the suite YAML (defaults to
Claude Opus 4.7 if none given and ANTHROPIC_API_KEY is set).
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path

from ..adapters import build_adapter
from ..adapters.base import Adapter
from ..config import SamplingParams, SuiteConfig
from ..schema import BenchmarkResult, ModelSpec, Prompt
from .base import Benchmark


DEFAULT_JUDGE = ModelSpec(
    provider="anthropic",
    adapter="anthropic",
    model="claude-opus-4-7",
    label="Judge (Claude Opus 4.7)",
)


JUDGE_PROMPT = """You are an impartial evaluator scoring AI model outputs.

PROMPT GIVEN TO THE MODEL:
{prompt}

MODEL'S RESPONSE:
{output}

RUBRIC:
{rubric}

Respond with a single JSON object and nothing else:
{{"score": <integer 1-10>, "reasoning": "<one sentence>"}}
"""


DEFAULT_RUBRIC = (
    "Rate the response on overall quality: correctness, clarity, completeness, and "
    "adherence to the prompt. 10 = excellent, 1 = poor or wrong."
)


def _parse_judge_output(text: str) -> tuple[int | None, str]:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None, text.strip()
    try:
        data = json.loads(match.group(0))
        score = int(data["score"])
        reasoning = str(data.get("reasoning", "")).strip()
        return score, reasoning
    except (ValueError, KeyError, TypeError):
        return None, text.strip()


class JudgeBenchmark(Benchmark):
    name = "quality_judge"

    def __init__(self, cfg: SuiteConfig):
        super().__init__(cfg)
        self.judge_spec = cfg.judge or DEFAULT_JUDGE

    async def run(
        self,
        adapter: Adapter,
        prompts: list[Prompt],
        *,
        sampling: SamplingParams,
        repetitions: int,
        output_dir: Path | None = None,
    ) -> list[BenchmarkResult]:
        judge = build_adapter(self.judge_spec)
        try:
            results: list[BenchmarkResult] = []
            for prompt in prompts:
                for rep in range(repetitions):
                    results.append(await self._one(adapter, judge, prompt, sampling, rep))
            return results
        finally:
            await judge.aclose()

    async def _one(
        self,
        adapter: Adapter,
        judge: Adapter,
        prompt: Prompt,
        sampling: SamplingParams,
        rep: int,
    ) -> BenchmarkResult:
        start = time.perf_counter()
        try:
            gen = await adapter.stream_generate(
                prompt.prompt,
                max_tokens=sampling.max_tokens,
                temperature=sampling.temperature,
                top_p=sampling.top_p,
            )
        except Exception as exc:  # noqa: BLE001
            return BenchmarkResult(
                benchmark=self.name,
                model=adapter.spec,
                duration_ms=(time.perf_counter() - start) * 1000,
                success=False,
                error=f"generation failed: {type(exc).__name__}: {exc}",
                prompt_id=prompt.id,
                metadata={"repetition": rep},
            )

        judge_input = JUDGE_PROMPT.format(
            prompt=prompt.prompt,
            output=gen.text,
            rubric=prompt.rubric or DEFAULT_RUBRIC,
        )
        try:
            judge_gen = await judge.stream_generate(
                judge_input, max_tokens=256, temperature=0.0, top_p=1.0
            )
        except Exception as exc:  # noqa: BLE001
            return BenchmarkResult(
                benchmark=self.name,
                model=adapter.spec,
                duration_ms=(time.perf_counter() - start) * 1000,
                success=False,
                error=f"judging failed: {type(exc).__name__}: {exc}",
                prompt_id=prompt.id,
                sample_output=gen.text,
                metadata={"repetition": rep},
            )

        score, reasoning = _parse_judge_output(judge_gen.text)
        elapsed_ms = (time.perf_counter() - start) * 1000
        return BenchmarkResult(
            benchmark=self.name,
            model=adapter.spec,
            duration_ms=elapsed_ms,
            success=score is not None,
            error=None if score is not None else "judge returned unparseable output",
            prompt_id=prompt.id,
            usage=gen.usage,
            sample_output=gen.text,
            score=float(score) if score is not None else None,
            score_reasoning=reasoning,
            metadata={
                "repetition": rep,
                "judge": self.judge_spec.display,
                "rubric": prompt.rubric or DEFAULT_RUBRIC,
            },
        )
