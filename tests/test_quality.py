import pytest

from benchman.adapters.base import Adapter, StreamedGeneration
from benchman.benchmarks.quality_exact import ExactMatchBenchmark, _matches
from benchman.benchmarks.quality_judge import JudgeBenchmark, _parse_judge_output
from benchman.config import SamplingParams, SuiteConfig
from benchman.schema import ModelSpec, Prompt, TokenUsage


class CannedAdapter(Adapter):
    def __init__(self, spec, *, text):
        super().__init__(spec)
        self._text = text

    async def stream_generate(self, prompt, **kw):
        return StreamedGeneration(text=self._text, events=[], usage=TokenUsage())


def test_matches_modes():
    assert _matches("the answer is 5 cents", "5 cents", "contains")
    assert not _matches("ten", "5 cents", "contains")
    assert _matches("5 cents", "5 cents", "exact")
    assert not _matches("  5 cents!", "5 cents", "exact")
    assert _matches("answer: 5", r"\d+", "regex")


def test_parse_judge_output_valid_json():
    score, reasoning = _parse_judge_output('Here: {"score": 8, "reasoning": "Clear and correct."}')
    assert score == 8
    assert reasoning == "Clear and correct."


def test_parse_judge_output_missing_json():
    score, reasoning = _parse_judge_output("I cannot score this.")
    assert score is None


@pytest.mark.asyncio
async def test_exact_match_scores_correctly():
    spec = ModelSpec(provider="fake", adapter="openai", model="fake")
    adapter = CannedAdapter(spec, text="The answer is 5 cents.")
    prompts = [
        Prompt(id="ok", prompt="?", expected="5 cents"),
        Prompt(id="fail", prompt="?", expected="1 dollar"),
        Prompt(id="skipped", prompt="?"),
    ]
    results = await ExactMatchBenchmark().run(
        adapter, prompts, sampling=SamplingParams(), repetitions=1
    )
    assert len(results) == 2  # skipped prompt has no expected
    by_id = {r.prompt_id: r for r in results}
    assert by_id["ok"].score == 1.0
    assert by_id["fail"].score == 0.0


@pytest.mark.asyncio
async def test_judge_scores_via_judge_adapter(monkeypatch):
    under_test_spec = ModelSpec(provider="fake", adapter="openai", model="fake")
    judge_spec = ModelSpec(provider="fake", adapter="openai", model="judge")

    adapter = CannedAdapter(under_test_spec, text="Paris is the capital of France.")
    judge_adapter = CannedAdapter(judge_spec, text='{"score": 9, "reasoning": "Correct."}')

    # monkeypatch build_adapter so JudgeBenchmark doesn't try to hit a real API
    import benchman.benchmarks.quality_judge as qj

    monkeypatch.setattr(qj, "build_adapter", lambda spec: judge_adapter)

    cfg = SuiteConfig(models=[under_test_spec], benchmarks=["quality_judge"], judge=judge_spec)
    results = await JudgeBenchmark(cfg).run(
        adapter,
        [Prompt(id="cap", prompt="What is the capital of France?")],
        sampling=SamplingParams(),
        repetitions=1,
    )
    assert len(results) == 1
    assert results[0].success
    assert results[0].score == 9.0
    assert results[0].score_reasoning == "Correct."
