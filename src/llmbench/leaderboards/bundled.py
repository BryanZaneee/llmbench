"""Bundled snapshot source. Ships with the package so `llmbench leaderboard` works offline."""

from __future__ import annotations

import json
from importlib.resources import files
from pathlib import Path

from .base import LeaderboardEntry, LeaderboardSnapshot, LeaderboardSource


class BundledSource(LeaderboardSource):
    name = "bundled"
    description = "Snapshot shipped with llmbench (works offline, may be stale)."
    requires_network = False
    cache_ttl_seconds = 10**9  # effectively never stale — it's a static file

    def fetch(self) -> LeaderboardSnapshot:
        data_path: Path
        try:
            data_path = Path(str(files("llmbench.data") / "bundled_leaderboard.json"))
        except (ModuleNotFoundError, FileNotFoundError):
            data_path = Path(__file__).parent.parent / "data" / "bundled_leaderboard.json"
        raw = json.loads(data_path.read_text())
        entries = [LeaderboardEntry(**e) for e in raw.get("entries", [])]
        snapshot_kwargs: dict = {
            "source": self.name,
            "source_url": raw.get("source_url"),
            "entries": entries,
        }
        if raw.get("fetched_at"):
            snapshot_kwargs["fetched_at"] = raw["fetched_at"]
        return LeaderboardSnapshot(**snapshot_kwargs)
