"""Measures streaming performance: TTFT, inter-chunk latency, and tokens per second."""

from __future__ import annotations

import time
from pathlib import Path

from ..adapters.base import Adapter
from ..config import SamplingParams
from ..schema import BenchmarkResult, Prompt, ThroughputMetrics
from .base import Benchmark


class ThroughputBenchmark(Benchmark):
    name = "throughput"

    async def run(
        self,
        adapter: Adapter,
        prompts: list[Prompt],
        *,
        sampling: SamplingParams,
        repetitions: int,
        output_dir: Path | None = None,
    ) -> list[BenchmarkResult]:
        results: list[BenchmarkResult] = []
        for prompt in prompts:
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
        start = time.perf_counter()
        try:
            gen = await adapter.stream_generate(
                prompt.prompt,
                max_tokens=sampling.max_tokens,
                temperature=sampling.temperature,
                top_p=sampling.top_p,
            )
        except Exception as exc:  # noqa: BLE001
            elapsed_ms = (time.perf_counter() - start) * 1000
            return BenchmarkResult(
                benchmark=self.name,
                model=adapter.spec,
                duration_ms=elapsed_ms,
                success=False,
                error=f"{type(exc).__name__}: {exc}",
                prompt_id=prompt.id,
                metadata={"repetition": rep},
            )
        end = time.perf_counter()

        total_ms = (end - start) * 1000
        ttft_ms: float | None = None
        inter_token_ms: float | None = None
        tok_per_s: float | None = None

        if gen.events:
            ttft_ms = (gen.events[0].timestamp - start) * 1000
            if len(gen.events) > 1:
                deltas = [
                    gen.events[i].timestamp - gen.events[i - 1].timestamp
                    for i in range(1, len(gen.events))
                ]
                inter_token_ms = (sum(deltas) / len(deltas)) * 1000
            # tok/s isolates generation speed — denominator excludes TTFT so a
            # slow-to-start but fast-generating model isn't penalized for warmup.
            gen_time = end - gen.events[0].timestamp
            out_tokens = gen.usage.output_tokens or len(gen.events)
            if gen_time > 0:
                tok_per_s = out_tokens / gen_time

        throughput = ThroughputMetrics(
            ttft_ms=ttft_ms,
            total_latency_ms=total_ms,
            output_tokens=gen.usage.output_tokens or len(gen.events),
            tokens_per_second=tok_per_s,
            inter_token_latency_ms=inter_token_ms,
        )
        return BenchmarkResult(
            benchmark=self.name,
            model=adapter.spec,
            duration_ms=total_ms,
            success=True,
            prompt_id=prompt.id,
            usage=gen.usage,
            throughput=throughput,
            sample_output=gen.text,
            metadata={"repetition": rep, "stop_reason": gen.stop_reason},
        )
