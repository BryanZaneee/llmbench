"""Runs every (model x benchmark) combination with bounded concurrency.

A suite = N models x M benchmarks. We fire off one task per pair, gated by a
semaphore so we don't DoS any single provider, and collect the results.
"""

from __future__ import annotations

import asyncio
import warnings
from pathlib import Path

import yaml

from . import __version__
from .adapters import adapter_class, build_adapter
from .benchmarks import get_benchmark
from .config import SuiteConfig
from .schema import BenchmarkResult, ModelSpec, Prompt, RunManifest

RESULTS_DIR = Path("results")


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
    output_dir = RESULTS_DIR / manifest.run_id

    sem = asyncio.Semaphore(cfg.concurrency)
    tasks = [
        _run_one(sem, spec, bench_name, prompts, cfg, output_dir)
        for spec in cfg.models
        for bench_name in cfg.benchmarks
        if _pair_runs(spec, bench_name, cfg)
    ]
    nested = await asyncio.gather(*tasks)

    results = [r for group in nested for r in group]
    for r in results:
        r.metadata["run_id"] = manifest.run_id
    return manifest, results


def _pair_runs(spec: ModelSpec, bench_name: str, cfg: SuiteConfig) -> bool:
    """Should this (model, benchmark) pair run?

    Two gates: the model's own `benchmarks:` allowlist, and whether the
    adapter can do what the benchmark needs. Without the second, a Flux model
    in a throughput suite raised NotImplementedError partway through the run.
    Capabilities come off the adapter class, since constructing one needs a
    key we should not demand for a pair we are about to skip.
    """
    if spec.benchmarks is not None and bench_name not in spec.benchmarks:
        return False
    needed = get_benchmark(bench_name, cfg).requires
    if needed in adapter_class(spec).capabilities:
        return True
    warnings.warn(
        f"Skipping {spec.display} x {bench_name}: the {spec.adapter!r} adapter "
        f"has no {needed.value} capability.",
        stacklevel=2,
    )
    return False


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
