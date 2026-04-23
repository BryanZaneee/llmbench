from pathlib import Path

from llmbench.reports.html import render_gallery
from llmbench.schema import (
    BenchmarkResult,
    ModelSpec,
    Prompt,
    RunManifest,
    ThroughputMetrics,
    TokenUsage,
)


def _result(model, prompt_id, **over):
    defaults = dict(
        benchmark="throughput",
        model=model,
        duration_ms=200.0,
        success=True,
        prompt_id=prompt_id,
        usage=TokenUsage(input_tokens=10, output_tokens=20),
        throughput=ThroughputMetrics(
            ttft_ms=50.0, total_latency_ms=200.0, output_tokens=20, tokens_per_second=100.0
        ),
        sample_output="An example completion.",
    )
    defaults.update(over)
    return BenchmarkResult(**defaults)


def test_gallery_writes_html_with_expected_sections(tmp_path: Path):
    m1 = ModelSpec(provider="anthropic", adapter="anthropic", model="claude", label="Claude")
    m2 = ModelSpec(provider="openai", adapter="openai", model="gpt", label="GPT")
    manifest = RunManifest(
        suite_version="0.1.0",
        models=[m1, m2],
        benchmarks=["throughput"],
        prompts=[Prompt(id="q1", prompt="Say hi")],
    )
    results = [
        _result(m1, "q1"),
        _result(m2, "q1", sample_output="Hi there!"),
    ]
    out_path = tmp_path / "gallery.html"
    render_gallery(manifest, results, out_path)
    html = out_path.read_text()
    assert "Claude" in html
    assert "GPT" in html
    assert "Say hi" in html
    assert "An example completion." in html
    assert "Hi there!" in html
