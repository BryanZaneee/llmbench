"""`llmbench view` resolves galleries straight off disk, with no index."""

from __future__ import annotations

import os

from typer.testing import CliRunner

from llmbench import cli

runner = CliRunner()


def _make_run(root, run_id, mtime):
    d = root / run_id
    d.mkdir(parents=True)
    gallery = d / "gallery.html"
    gallery.write_text(f"<h1>{run_id}</h1>")
    os.utime(gallery, (mtime, mtime))
    return gallery


def test_latest_picks_newest_by_mtime(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "RESULTS_DIR", tmp_path)
    _make_run(tmp_path, "old", 1_000_000)
    _make_run(tmp_path, "new", 2_000_000)
    opened = []
    monkeypatch.setattr(cli.webbrowser, "open", opened.append)

    result = runner.invoke(cli.app, ["view", "--latest"])

    assert result.exit_code == 0
    assert opened and opened[0].endswith("new/gallery.html")


def test_explicit_run_id(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "RESULTS_DIR", tmp_path)
    _make_run(tmp_path, "abc123", 1_000_000)
    opened = []
    monkeypatch.setattr(cli.webbrowser, "open", opened.append)

    assert runner.invoke(cli.app, ["view", "abc123"]).exit_code == 0
    assert opened[0].endswith("abc123/gallery.html")


def test_missing_run_and_no_args_both_exit_1(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "RESULTS_DIR", tmp_path)
    assert runner.invoke(cli.app, ["view", "nope"]).exit_code == 1
    assert runner.invoke(cli.app, ["view", "--latest"]).exit_code == 1
    assert runner.invoke(cli.app, ["view"]).exit_code == 1
