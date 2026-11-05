"""Guided Image Bench uses selected models and a single shared prompt, offline."""
from typer.testing import CliRunner

from llmbench import cli
from llmbench.schema import ModelSpec

runner = CliRunner()


def setup_models(monkeypatch):
    models = [ModelSpec(provider="openai", adapter="openai_compat", model="image-one",
                        benchmarks=["image_gen"]),
              ModelSpec(provider="flux", adapter="flux", model="image-two"),
              ModelSpec(provider="anthropic", adapter="anthropic", model="text")]
    monkeypatch.setattr(cli.cfgmod, "config_models", lambda: models)
    calls = []
    monkeypatch.setattr(cli, "_execute", lambda *args, **kwargs: calls.append((args, kwargs)))
    return calls


def test_menu_blank_prompt_runs_all_image_models(monkeypatch):
    calls = setup_models(monkeypatch)
    result = runner.invoke(cli.app, [], input="2\n1\n1\n\ny\n")
    assert result.exit_code == 0, result.output
    args, kwargs = calls[0]
    assert len(args[0].models) == 2
    assert args[0].benchmarks == ["image_gen"]
    assert args[0].repetitions == 1
    assert kwargs["prompts"][0].prompt == cli.DEFAULT_IMAGE_PROMPT


def test_select_and_add_models_then_use_custom_prompt(monkeypatch):
    calls = setup_models(monkeypatch)
    result = runner.invoke(cli.app, [], input=
                           "2\n1\n3\n2\n2\ngemini\ngemini\nimage-three\n\n1\nA blue bird\ny\n")
    assert result.exit_code == 0, result.output
    args, kwargs = calls[0]
    assert [m.model for m in args[0].models] == ["image-two", "image-three"]
    assert kwargs["prompts"][0].prompt == "A blue bird"


def test_published_leaderboards_dont_run_models(monkeypatch):
    calls = setup_models(monkeypatch)
    result = runner.invoke(cli.app, [], input="1\nbundled\n")
    assert result.exit_code == 0, result.output
    assert "Leaderboard" in result.output
    assert not calls


def test_direct_image_bench_custom_and_default_prompt(monkeypatch):
    calls = setup_models(monkeypatch)
    for options, expected in [([], cli.DEFAULT_IMAGE_PROMPT), (["--prompt", "A dog"], "A dog")]:
        result = runner.invoke(cli.app, ["image-bench", *options])
        assert result.exit_code == 0, result.output
        assert calls[-1][0][3][0].prompt == expected


def test_cancel_and_empty_selection_never_run(monkeypatch):
    calls = setup_models(monkeypatch)
    result = runner.invoke(cli.app, [], input="2\n1\n3\nnone\n1\n4\n")
    assert result.exit_code == 0, result.output
    assert "Add at least one" in result.output
    assert not calls


def test_image_bench_writes_gallery_with_shared_prompt(tmp_path, monkeypatch):
    import json

    from llmbench import runner as pipeline
    from test_image_gen import FakeImageAdapter

    models = [ModelSpec(provider="fake", adapter="openai_compat", model="one"),
              ModelSpec(provider="fake", adapter="openai_compat", model="two")]
    monkeypatch.setattr(cli.cfgmod, "config_models", lambda: models)
    monkeypatch.setattr(cli, "RESULTS_DIR", tmp_path)
    monkeypatch.setattr(pipeline, "RESULTS_DIR", tmp_path)
    received = []

    class RecordingAdapter(FakeImageAdapter):
        async def generate_image(self, prompt, **kwargs):
            received.append(prompt)
            return await super().generate_image(prompt, **kwargs)

    monkeypatch.setattr(pipeline, "build_adapter", RecordingAdapter)
    result = runner.invoke(cli.app, ["image-bench", "--prompt", "A mountain cat", "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert received == ["A mountain cat", "A mountain cat"]
    assert len(payload["results"]) == 2
    assert all(row["success"] for row in payload["results"])
    gallery = tmp_path / payload["run_id"] / "gallery.html"
    assert gallery.exists()
    assert "A mountain cat" in gallery.read_text()
    assert len(list(tmp_path.glob("*/images/*/*.png"))) == 2
