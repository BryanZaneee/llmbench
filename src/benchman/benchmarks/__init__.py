from __future__ import annotations

from ..config import SuiteConfig
from .base import Benchmark
from .image_gen import ImageGenBenchmark
from .quality_exact import ExactMatchBenchmark
from .quality_judge import JudgeBenchmark
from .throughput import ThroughputBenchmark

_REGISTRY: dict[str, type[Benchmark]] = {
    "throughput": ThroughputBenchmark,
    "quality_exact": ExactMatchBenchmark,
    "quality_judge": JudgeBenchmark,
    "image_gen": ImageGenBenchmark,
}


def get_benchmark(name: str, cfg: SuiteConfig) -> Benchmark:
    cls = _REGISTRY.get(name)
    if cls is None:
        raise ValueError(f"Unknown benchmark: {name!r}. Known: {sorted(_REGISTRY)}")
    return cls(cfg)


__all__ = [
    "Benchmark",
    "ExactMatchBenchmark",
    "ImageGenBenchmark",
    "JudgeBenchmark",
    "ThroughputBenchmark",
    "get_benchmark",
]
