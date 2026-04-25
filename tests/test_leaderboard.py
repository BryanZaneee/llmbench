import json
from datetime import datetime, timedelta, timezone

import httpx
import pytest

from llmbench.leaderboards import (
    AiderLeaderboard,
    BundledSource,
    HuggingFaceLeaderboard,
    available_sources,
    get_source,
)
from llmbench.leaderboards.base import LeaderboardEntry, LeaderboardSnapshot
from llmbench.leaderboards.cache import (
    get_snapshot,
    is_fresh,
    load_cached,
    save_cached,
)


def test_registry_exposes_known_sources():
    names = available_sources()
    assert "huggingface" in names
    assert "lmarena" in names
    assert "bundled" in names
    assert "aider" in names


def test_bundled_source_works_offline():
    snap = BundledSource().fetch()
    assert snap.source == "bundled"
    assert len(snap.entries) > 0
    e = snap.entries[0]
    assert e.model_id
    assert e.display_name
    assert isinstance(e.metrics, dict)


def test_huggingface_parses_json_response(monkeypatch):
    fake_payload = {
        "rows": [
            {
                "row": {
                    "Model": '<a href="x">anthropic/claude-opus-4-7</a>',
                    "fullname": "anthropic/claude-opus-4-7",
                    "Flagged": False,
                    "Average ⬆️": 82.5,
                    "IFEval": 89.0,
                    "BBH": 78.0,
                    "MATH Lvl 5": 61.2,
                    "GPQA": 55.3,
                    "MUSR": 70.1,
                    "MMLU-PRO": 77.4,
                    "#Params (B)": None,
                    "Hub License": "proprietary",
                    "Precision": "n/a",
                }
            }
        ]
    }

    def mock_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=fake_payload)

    transport = httpx.MockTransport(mock_handler)
    RealClient = httpx.Client

    import llmbench.leaderboards.huggingface as hf_mod
    monkeypatch.setattr(
        hf_mod.httpx,
        "Client",
        lambda *args, **kwargs: RealClient(transport=transport, timeout=10),
    )

    snap = HuggingFaceLeaderboard(top_n=1).fetch()
    assert len(snap.entries) == 1
    entry = snap.entries[0]
    assert entry.model_id == "anthropic/claude-opus-4-7"
    assert entry.organization == "anthropic"
    assert entry.metrics["mmlu_pro"] == 77.4
    assert entry.source == "huggingface"


def test_aider_parses_yaml_response(monkeypatch):
    fake_yaml = """
- dirname: 2026-01-15--claude-opus-4-7
  test_cases: 225
  model: claude-opus-4-7
  edit_format: diff
  pass_rate_1: 70.5
  pass_rate_2: 79.0
  percent_cases_well_formed: 99.2
  released: 2026-01-15
- dirname: 2026-01-10--gpt-5
  test_cases: 225
  model: gpt-5
  edit_format: diff
  pass_rate_1: 65.3
  pass_rate_2: 74.1
  percent_cases_well_formed: 98.4
  released: 2026-01-10
- dirname: 2025-12-01--no-pass-rate
  test_cases: 225
  model: model-without-pass-rate
  edit_format: diff
  percent_cases_well_formed: 50.0
"""

    def mock_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=fake_yaml)

    transport = httpx.MockTransport(mock_handler)
    RealClient = httpx.Client

    import llmbench.leaderboards.aider as aider_mod
    monkeypatch.setattr(
        aider_mod.httpx,
        "Client",
        lambda *args, **kwargs: RealClient(transport=transport, timeout=10),
    )

    snap = AiderLeaderboard().fetch()
    assert snap.source == "aider"
    # Third row had no pass_rate_2 — should be filtered out.
    assert len(snap.entries) == 2
    # Sorted descending by pass_rate_2.
    assert snap.entries[0].model_id == "claude-opus-4-7"
    assert snap.entries[0].rank == 1
    assert snap.entries[0].metrics["polyglot_pass_rate"] == 79.0
    assert snap.entries[0].metrics["polyglot_correct_edits"] == 99.2
    assert snap.entries[0].organization == "anthropic"
    assert snap.entries[1].model_id == "gpt-5"
    assert snap.entries[1].organization == "openai"


def test_cache_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    snap = LeaderboardSnapshot(
        source="test-src",
        entries=[LeaderboardEntry(
            model_id="x", display_name="x", organization="x", source="test-src"
        )],
    )
    save_cached(snap)
    loaded = load_cached("test-src")
    assert loaded is not None
    assert loaded.entries[0].model_id == "x"


def test_is_fresh_window():
    stale = LeaderboardSnapshot(
        source="t",
        fetched_at=datetime.now(timezone.utc) - timedelta(hours=48),
    )
    fresh = LeaderboardSnapshot(source="t")
    assert not is_fresh(stale, ttl_seconds=24 * 3600)
    assert is_fresh(fresh, ttl_seconds=24 * 3600)


def test_get_snapshot_prefers_cache_within_ttl(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    src = BundledSource()
    # Bundled source TTL is effectively infinite, so a saved cache will be used.
    snap1 = get_snapshot(src)
    snap2 = get_snapshot(src)
    assert snap1.fetched_at == snap2.fetched_at


def test_offline_mode_requires_cache(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))

    class DummySource(BundledSource):
        name = "dummy-never-cached"

    with pytest.raises(RuntimeError):
        get_snapshot(DummySource(), offline=True)
