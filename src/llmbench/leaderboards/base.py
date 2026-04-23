"""Source contract + shared data shapes for published leaderboards.

Each source (HuggingFace Open LLM Leaderboard, LMArena, bundled snapshot) is
a subclass of `LeaderboardSource` that returns a `LeaderboardSnapshot`.
Metrics are a free-form dict[str, float] because each source publishes
different columns — the CLI renders whatever is present.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


def _now() -> datetime:
    return datetime.now(timezone.utc)


class LeaderboardEntry(BaseModel):
    model_id: str
    display_name: str
    organization: str
    source: str
    metrics: dict[str, float] = Field(default_factory=dict)
    rank: int | None = None
    source_url: str | None = None
    extra: dict[str, Any] = Field(default_factory=dict)


class LeaderboardSnapshot(BaseModel):
    source: str
    source_url: str | None = None
    fetched_at: datetime = Field(default_factory=_now)
    entries: list[LeaderboardEntry] = Field(default_factory=list)


class LeaderboardSource(ABC):
    name: str
    description: str
    requires_network: bool = True
    cache_ttl_seconds: int = 24 * 3600

    @abstractmethod
    def fetch(self) -> LeaderboardSnapshot:
        """Fetch the latest snapshot from the source."""
