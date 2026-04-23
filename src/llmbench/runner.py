"""Runs every (model x benchmark) combination with bounded concurrency.

A suite = N models x M benchmarks. We fire off one task per pair, gated by a
semaphore so we don't DoS any single provider, and collect the results.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import yaml

from . import __version__
from .adapters import build_adapter
from .benchmarks import get_benchmark
from .config import SuiteConfig
from .schema import BenchmarkResult, ModelSpec, Prompt, RunManifest


DEFAULT_PROMPTS: list[Prompt] = [
    Prompt(id="short", prompt="Write a one-sentence description of the sun."),
    Prompt(
        id="medium",
        prompt="Explain how a transformer attention head works in roughly 150 words.",
    ),
    Prompt(id="long", prompt="Write a 400-word fictional story about a lighthouse keeper in 1890."),
]


def load_prompts(path: str | None) -> list[Prompt]:
    if not path:
        return DEFAULT_PROMPTS
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Prompts file not found: {p}")
    data = yaml.safe_load(p.read_text())
    return [Prompt.model_validate(item) for item in data]


async def run_suite(cfg: SuiteConfig) -> tuple[RunManifest, list[BenchmarkResult]]:
    prompts = load_prompts(cfg.prompts_file)
    manifest = RunManifest(
        suite_version=__version__,
        models=cfg.models,
        benchmarks=cfg.benchmarks,
        prompts=prompts,
    )
    output_dir = Path(cfg.results_dir) / manifest.run_id

    sem = asyncio.Semaphore(cfg.concurrency)
    tasks = [
        _run_one(sem, spec, bench_name, prompts, cfg, output_dir)
        for spec in cfg.models
        for bench_name in cfg.benchmarks
        if spec.benchmarks is None or bench_name in spec.benchmarks
    ]
    nested = await asyncio.gather(*tasks)

    results = [r for group in nested for r in group]
    for r in results:
        r.metadata["run_id"] = manifest.run_id
    return manifest, results


async def _run_one(
    sem: asyncio.Semaphore,
    spec: ModelSpec,
    bench_name: str,
    prompts: list[Prompt],
    cfg: SuiteConfig,
    output_dir: Path,
) -> list[BenchmarkResult]:
    async with sem:
        adapter = build_adapter(spec)
        bench = get_benchmark(bench_name, cfg)
        try:
            return await bench.run(
                adapter,
                prompts,
                sampling=cfg.sampling,
                repetitions=cfg.repetitions,
                output_dir=output_dir,
            )
        finally:
            await adapter.aclose()
