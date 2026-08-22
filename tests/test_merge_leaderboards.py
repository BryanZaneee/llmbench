"""The daily refresh must survive a source failing upstream."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

_spec = importlib.util.spec_from_file_location(
    "merge_leaderboards",
    Path(__file__).resolve().parents[1] / "scripts" / "merge_leaderboards.py",
)
merge_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(merge_mod)


def _snapshot(dirpath: Path, name: str, count: int) -> None:
    (dirpath / f"{name}.json").write_text(
        json.dumps(
            {
                "source": name,
                "source_url": f"https://example.test/{name}",
                "fetched_at": "2026-08-22T00:00:00+00:00",
                "entries": [{"model_id": f"{name}-{i}"} for i in range(count)],
            }
        )
    )


def test_missing_and_empty_snapshots_are_skipped_not_fatal(tmp_path):
    _snapshot(tmp_path, "lmarena", 3)
    (tmp_path / "huggingface.json").write_text("")  # source failed, empty file
    # aider.json and bundled.json never written at all

    merged = merge_mod.merge(tmp_path, merge_mod.SOURCES)

    assert [s["source"] for s in merged["sources"]] == ["lmarena"]
    assert len(merged["entries"]) == 3


def test_corrupt_snapshot_is_skipped(tmp_path):
    _snapshot(tmp_path, "bundled", 2)
    (tmp_path / "aider.json").write_text("{not json")

    merged = merge_mod.merge(tmp_path, merge_mod.SOURCES)

    assert [s["source"] for s in merged["sources"]] == ["bundled"]


def test_every_source_failing_refuses_to_write(tmp_path):
    with pytest.raises(SystemExit):
        merge_mod.merge(tmp_path, merge_mod.SOURCES)
