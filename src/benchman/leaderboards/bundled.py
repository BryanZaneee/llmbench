"""Bundled snapshot source. Ships with the package so `benchman leaderboard` works offline."""

from __future__ import annotations

import json
from importlib.resources import files
from pathlib import Path

from .base import LeaderboardEntry, LeaderboardSnapshot, LeaderboardSource


class BundledSource(LeaderboardSource):
    name = "bundled"
    description = "Snapshot shipped with benchman (works offline, may be stale)."
    requires_network = False
    cache_ttl_seconds = 10**9  # effectively never stale — it's a static file

    def fetch(self) -> LeaderboardSnapshot:
        data_path: Path
        try:
            data_path = Path(str(files("benchman.data") / "bundled_leaderboard.json"))
        except (ModuleNotFoundError, FileNotFoundError):
            data_path = Path(__file__).parent.parent / "data" / "bundled_leaderboard.json"
        raw = json.loads(data_path.read_text())
        entries = [LeaderboardEntry(**e) for e in raw.get("entries", [])]
        return LeaderboardSnapshot(
            source=self.name,
            source_url=raw.get("source_url"),
            fetched_at=raw.get("fetched_at") or "1970-01-01T00:00:00+00:00",
            entries=entries,
        )
