from benchman.schema import BenchmarkResult, ModelSpec, ThroughputMetrics, TokenUsage


def test_model_spec_display_defaults_to_provider_model():
    spec = ModelSpec(provider="anthropic", adapter="anthropic", model="claude-opus-4-7")
    assert spec.display == "anthropic/claude-opus-4-7"


def test_model_spec_display_uses_label_when_set():
    spec = ModelSpec(
        provider="anthropic", adapter="anthropic", model="claude-opus-4-7", label="Opus"
    )
    assert spec.display == "Opus"


def test_token_usage_total():
    u = TokenUsage(input_tokens=10, output_tokens=25)
    assert u.total == 35


def test_benchmark_result_roundtrips_json():
    r = BenchmarkResult(
        benchmark="throughput",
        model=ModelSpec(provider="p", adapter="openai", model="m"),
        duration_ms=123.4,
        success=True,
        throughput=ThroughputMetrics(total_latency_ms=123.4, output_tokens=50, tokens_per_second=40.5),
    )
    data = r.model_dump_json()
    roundtrip = BenchmarkResult.model_validate_json(data)
    assert roundtrip.throughput is not None
    assert roundtrip.throughput.tokens_per_second == 40.5
