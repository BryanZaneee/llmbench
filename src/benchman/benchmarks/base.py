"""Benchmark contract. A benchmark runs against one adapter and returns a list of results."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from ..adapters.base import Adapter
from ..config import SamplingParams, SuiteConfig
from ..schema import BenchmarkResult, Prompt


class Benchmark(ABC):
    name: str

    def __init__(self, cfg: SuiteConfig | None = None):
        self.cfg = cfg

    @abstractmethod
    async def run(
        self,
        adapter: Adapter,
        prompts: list[Prompt],
        *,
        sampling: SamplingParams,
        repetitions: int,
        output_dir: Path | None = None,
    ) -> list[BenchmarkResult]:
        """Run the benchmark against one adapter. output_dir is the per-run artifact dir."""
