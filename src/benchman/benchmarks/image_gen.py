"""Image generation benchmark. Records latency and writes PNGs for human review.

PNGs land at: <output_dir>/images/<model_slug>/<prompt_id>__rep<N>.png
The gallery renderer picks them up via result.image_paths.
"""

from __future__ import annotations

import time
from pathlib import Path

from ..adapters.base import Adapter
from ..config import SamplingParams
from ..schema import BenchmarkResult, Prompt
from .base import Benchmark


class ImageGenBenchmark(Benchmark):
    name = "image_gen"

    async def run(
        self,
        adapter: Adapter,
        prompts: list[Prompt],
        *,
        sampling: SamplingParams,
        repetitions: int,
        output_dir: Path | None = None,
    ) -> list[BenchmarkResult]:
        if output_dir is None:
            raise ValueError("image_gen requires output_dir for saving PNGs")
        img_dir = output_dir / "images" / adapter.spec.slug()
        img_dir.mkdir(parents=True, exist_ok=True)

        results: list[BenchmarkResult] = []
        for prompt in prompts:
            for rep in range(repetitions):
                results.append(await self._one(adapter, prompt, rep, img_dir))
        return results

    async def _one(
        self, adapter: Adapter, prompt: Prompt, rep: int, img_dir: Path
    ) -> BenchmarkResult:
        start = time.perf_counter()
        try:
            result = await adapter.generate_image(prompt.prompt)
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

        paths: list[str] = []
        for i, img_bytes in enumerate(result.images):
            suffix = "" if len(result.images) == 1 else f"_{i}"
            path = img_dir / f"{prompt.id}__rep{rep}{suffix}.png"
            path.write_bytes(img_bytes)
            paths.append(str(path))

        return BenchmarkResult(
            benchmark=self.name,
            model=adapter.spec,
            duration_ms=elapsed_ms,
            success=True,
            prompt_id=prompt.id,
            image_paths=paths,
            metadata={
                "repetition": rep,
                "width": result.width,
                "height": result.height,
                "n_images": len(result.images),
            },
        )
