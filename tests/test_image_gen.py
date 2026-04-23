import pytest

from benchman.adapters.base import Adapter, ImageResult
from benchman.benchmarks.image_gen import ImageGenBenchmark
from benchman.config import SamplingParams
from benchman.schema import ModelSpec, Prompt

# 1x1 transparent PNG
_PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc\xf8\xcf"
    b"\xc0\xf0\x1f\x00\x05\x00\x01\xff\xa1\xf9\x97\xd2\x00\x00\x00\x00IEND\xaeB`\x82"
)


class FakeImageAdapter(Adapter):
    def __init__(self, spec):
        super().__init__(spec)

    async def stream_generate(self, prompt, **kw):
        raise NotImplementedError

    async def generate_image(self, prompt, **kwargs):
        return ImageResult(images=[_PNG_BYTES], width=1, height=1)


@pytest.mark.asyncio
async def test_image_gen_writes_pngs_and_records_paths(tmp_path):
    spec = ModelSpec(provider="fake", adapter="openai", model="fake-image")
    adapter = FakeImageAdapter(spec)
    prompts = [Prompt(id="cat", prompt="a cat on a rug")]
    results = await ImageGenBenchmark().run(
        adapter,
        prompts,
        sampling=SamplingParams(),
        repetitions=2,
        output_dir=tmp_path,
    )
    assert len(results) == 2
    for r in results:
        assert r.success
        assert len(r.image_paths) == 1
        from pathlib import Path
        p = Path(r.image_paths[0])
        assert p.exists()
        assert p.read_bytes() == _PNG_BYTES


@pytest.mark.asyncio
async def test_image_gen_requires_output_dir():
    spec = ModelSpec(provider="fake", adapter="openai", model="fake-image")
    with pytest.raises(ValueError):
        await ImageGenBenchmark().run(
            FakeImageAdapter(spec), [], sampling=SamplingParams(), repetitions=1
        )
