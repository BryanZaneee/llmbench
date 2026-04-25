from __future__ import annotations

from .aider import AiderLeaderboard
from .base import LeaderboardEntry, LeaderboardSource, LeaderboardSnapshot
from .bundled import BundledSource
from .huggingface import HuggingFaceLeaderboard
from .lmarena import LMArenaLeaderboard

_REGISTRY: dict[str, type[LeaderboardSource]] = {
    "aider": AiderLeaderboard,
    "bundled": BundledSource,
    "huggingface": HuggingFaceLeaderboard,
    "lmarena": LMArenaLeaderboard,
}


def get_source(name: str) -> LeaderboardSource:
    cls = _REGISTRY.get(name)
    if cls is None:
        raise ValueError(f"Unknown source: {name!r}. Known: {sorted(_REGISTRY)}")
    return cls()


def available_sources() -> list[str]:
    return sorted(_REGISTRY)


__all__ = [
    "AiderLeaderboard",
    "BundledSource",
    "HuggingFaceLeaderboard",
    "LMArenaLeaderboard",
    "LeaderboardEntry",
    "LeaderboardSnapshot",
    "LeaderboardSource",
    "available_sources",
    "get_source",
]
