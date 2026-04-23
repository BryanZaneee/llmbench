import asyncio
import time

import pytest

from benchman.adapters.base import Adapter, GenerationEvent, StreamedGeneration
from benchman.benchmarks.throughput import ThroughputBenchmark
from benchman.config import SamplingParams
from benchman.schema import Capability, ModelSpec, Prompt, TokenUsage


class FakeAdapter(Adapter):
    capabilities = {Capability.TEXT}

    def __init__(self, spec, *, chunks, per_chunk_delay, usage):
        super().__init__(spec)
        self._chunks = chunks
        self._delay = per_chunk_delay
        self._usage = usage

    async def stream_generate(self, prompt, *, max_tokens, temperature, top_p):
        events = []
        for c in self._chunks:
            await asyncio.sleep(self._delay)
            events.append(GenerationEvent(text=c, timestamp=time.perf_counter()))
        return StreamedGeneration(
            text="".join(self._chunks),
            events=events,
            usage=self._usage,
            stop_reason="end_turn",
        )


@pytest.mark.asyncio
async def test_throughput_computes_ttft_and_tokps():
    spec = ModelSpec(provider="fake", adapter="openai", model="fake")
    adapter = FakeAdapter(
        spec,
        chunks=["Hello ", "world", "!"],
        per_chunk_delay=0.01,
        usage=TokenUsage(input_tokens=5, output_tokens=3),
    )
    bench = ThroughputBenchmark()
    results = await bench.run(
        adapter, [Prompt(id="p1", prompt="hi")], sampling=SamplingParams(), repetitions=1
    )
    assert len(results) == 1
    r = results[0]
    assert r.success
    assert r.throughput.ttft_ms > 0
    assert r.throughput.tokens_per_second > 0
    assert r.usage.output_tokens == 3


@pytest.mark.asyncio
async def test_throughput_records_errors():
    class BrokenAdapter(Adapter):
        async def stream_generate(self, prompt, **kw):
            raise RuntimeError("boom")

    spec = ModelSpec(provider="fake", adapter="openai", model="fake")
    bench = ThroughputBenchmark()
    results = await bench.run(
        BrokenAdapter(spec),
        [Prompt(id="p1", prompt="hi")],
        sampling=SamplingParams(),
        repetitions=1,
    )
    assert results[0].success is False
    assert "boom" in results[0].error
