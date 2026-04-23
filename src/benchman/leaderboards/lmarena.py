"""LMArena (chatbot-arena) leaderboard fetcher.

Downloads the `latest` parquet file from the `lmarena-ai/leaderboard-dataset`
HuggingFace dataset and parses it with pyarrow. Default category is `text`
(standard text-only arena); others available via the `category` constructor arg.
"""

from __future__ import annotations

import io

import httpx

from .base import LeaderboardEntry, LeaderboardSnapshot, LeaderboardSource


SOURCE_URL = "https://lmarena.ai/leaderboard"


def _parquet_url(category: str) -> str:
    return (
        "https://huggingface.co/datasets/lmarena-ai/leaderboard-dataset/"
        f"resolve/main/{category}/latest-00000-of-00001.parquet"
    )


class LMArenaLeaderboard(LeaderboardSource):
    name = "lmarena"
    description = "LMArena ELO ratings from human preference voting (text category by default)"

    VALID_CATEGORIES = {
        "text",
        "text_style_control",
        "vision",
        "vision_style_control",
        "webdev",
        "search",
        "search_style_control",
        "document",
        "document_style_control",
        "text_to_image",
        "image_edit",
        "text_to_video",
        "image_to_video",
        "video_edit",
    }

    def __init__(self, *, category: str = "text") -> None:
        if category not in self.VALID_CATEGORIES:
            raise ValueError(
                f"Unknown LMArena category {category!r}. "
                f"Valid: {sorted(self.VALID_CATEGORIES)}"
            )
        self.category = category

    def fetch(self) -> LeaderboardSnapshot:
        try:
            import pyarrow.parquet as pq
        except ImportError as exc:
            raise RuntimeError(
                "LMArena source requires pyarrow. Install with: pip install pyarrow"
            ) from exc

        with httpx.Client(timeout=60, follow_redirects=True) as client:
            r = client.get(_parquet_url(self.category))
            r.raise_for_status()
            table = pq.read_table(io.BytesIO(r.content))

        # The `latest` parquet contains per-date snapshots of every model.
        # Keep only the most recent publish_date per model_name.
        rows = table.to_pylist()
        latest_per_model: dict[str, dict] = {}
        for row in rows:
            name = row.get("model_name") or ""
            if not name or row.get("rating") is None:
                continue
            published = row.get("leaderboard_publish_date") or ""
            prev = latest_per_model.get(name)
            if prev is None or (published > (prev.get("leaderboard_publish_date") or "")):
                latest_per_model[name] = row

        entries: list[LeaderboardEntry] = []
        for name, row in latest_per_model.items():
            metrics: dict[str, float] = {"elo": float(row["rating"])}
            if row.get("rating_lower") is not None:
                metrics["elo_lower"] = float(row["rating_lower"])
            if row.get("rating_upper") is not None:
                metrics["elo_upper"] = float(row["rating_upper"])
            entries.append(
                LeaderboardEntry(
                    model_id=name,
                    display_name=name,
                    organization=row.get("organization") or "unknown",
                    source="lmarena",
                    metrics=metrics,
                    rank=int(row["rank"]) if row.get("rank") is not None else None,
                    source_url=SOURCE_URL,
                    extra={
                        "vote_count": row.get("vote_count"),
                        "license": row.get("license"),
                        "category": self.category,
                        "published": row.get("leaderboard_publish_date"),
                    },
                )
            )
        # Re-rank by elo since the raw `rank` column is per-snapshot.
        entries.sort(key=lambda e: -e.metrics.get("elo", 0.0))
        for i, e in enumerate(entries, 1):
            e.rank = i
        return LeaderboardSnapshot(
            source=self.name,
            source_url=SOURCE_URL,
            entries=entries,
        )
