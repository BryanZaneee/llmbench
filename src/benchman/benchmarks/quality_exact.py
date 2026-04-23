"""Deterministic quality check. Scores 1.0 if the output matches `expected`, else 0.0.

Supports three match modes via the prompt's `check` field:
  - exact:    output.strip() == expected.strip()
  - contains: expected.lower() in output.lower()           (default)
  - regex:    re.search(expected, output) is not None
"""

from __future__ import annotations

import re
import time
from pathlib import Path

from ..adapters.base import Adapter
from ..config import SamplingParams
from ..schema import BenchmarkResult, Prompt
from .base import Benchmark


def _matches(output: str, expected: str, check: str) -> bool:
    if check == "exact":
        return output.strip() == expected.strip()
    if check == "regex":
        return re.search(expected, output) is not None
    return expected.lower() in output.lower()


class ExactMatchBenchmark(Benchmark):
    name = "quality_exact"

    async def run(
        self,
        adapter: Adapter,
        prompts: list[Prompt],
        *,
        sampling: SamplingParams,
        repetitions: int,
        output_dir: Path | None = None,
    ) -> list[BenchmarkResult]:
        scoreable = [p for p in prompts if p.expected is not None]
        results: list[BenchmarkResult] = []
        for prompt in scoreable:
            for rep in range(repetitions):
                results.append(await self._one(adapter, prompt, sampling, rep))
        return results

    async def _one(
        self,
        adapter: Adapter,
        prompt: Prompt,
        sampling: SamplingParams,
        rep: int,
    ) -> BenchmarkResult:
        assert prompt.expected is not None
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
                error=f"{type(exc).__name__}: {exc}",
                prompt_id=prompt.id,
                metadata={"repetition": rep},
            )
        elapsed_ms = (time.perf_counter() - start) * 1000
        passed = _matches(gen.text, prompt.expected, prompt.check)
        return BenchmarkResult(
            benchmark=self.name,
            model=adapter.spec,
            duration_ms=elapsed_ms,
            success=True,
            prompt_id=prompt.id,
            usage=gen.usage,
            sample_output=gen.text,
            score=1.0 if passed else 0.0,
            metadata={
                "repetition": rep,
                "check": prompt.check,
                "expected": prompt.expected,
                "passed": passed,
            },
        )
