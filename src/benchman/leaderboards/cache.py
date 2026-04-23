"""On-disk cache for leaderboard snapshots with TTL.

Lives at ~/.cache/benchman/leaderboards/<source>.json. Cache is a simple JSON
file containing the pydantic-dumped LeaderboardSnapshot; we decide freshness
by comparing `fetched_at` against the source's `cache_ttl_seconds`.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .base import LeaderboardSnapshot, LeaderboardSource


def cache_dir() -> Path:
    root = os.environ.get("XDG_CACHE_HOME") or str(Path.home() / ".cache")
    p = Path(root) / "benchman" / "leaderboards"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _cache_path(source_name: str) -> Path:
    return cache_dir() / f"{source_name}.json"


def load_cached(source_name: str) -> LeaderboardSnapshot | None:
    path = _cache_path(source_name)
    if not path.exists():
        return None
    try:
        return LeaderboardSnapshot.model_validate_json(path.read_text())
    except Exception:  # noqa: BLE001
        return None


def save_cached(snapshot: LeaderboardSnapshot) -> Path:
    path = _cache_path(snapshot.source)
    path.write_text(snapshot.model_dump_json(indent=2))
    return path


def is_fresh(snapshot: LeaderboardSnapshot, ttl_seconds: int) -> bool:
    age = datetime.now(timezone.utc) - snapshot.fetched_at
    return age < timedelta(seconds=ttl_seconds)


def get_snapshot(
    source: LeaderboardSource,
    *,
    refresh: bool = False,
    offline: bool = False,
) -> LeaderboardSnapshot:
    """Return a snapshot, using the cache when appropriate.

    Priority:
      - offline=True -> cache only (raise if missing)
      - refresh=True -> live fetch, update cache
      - otherwise: return cache if fresh, else live fetch
    """
    cached = load_cached(source.name)

    if offline:
        if cached is None:
            raise RuntimeError(
                f"No cached data for source {source.name!r} and --offline set"
            )
        return cached

    if not refresh and cached is not None and is_fresh(cached, source.cache_ttl_seconds):
        return cached

    snapshot = source.fetch()
    save_cached(snapshot)
    return snapshot
