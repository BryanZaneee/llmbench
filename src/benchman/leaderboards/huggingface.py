"""HuggingFace Open LLM Leaderboard v2 fetcher.

Uses the datasets-server JSON API at datasets-server.huggingface.co, which
paginates in chunks of <=100 rows. Primary columns: IFEval, BBH, MATH Lvl 5,
GPQA, MUSR, MMLU-PRO, plus an overall Average.
"""

from __future__ import annotations

import re
from typing import Any

import httpx

from .base import LeaderboardEntry, LeaderboardSnapshot, LeaderboardSource


BASE_URL = "https://datasets-server.huggingface.co/rows"
DATASET = "open-llm-leaderboard/contents"
PAGE_SIZE = 100
SOURCE_URL = "https://huggingface.co/spaces/open-llm-leaderboard/open_llm_leaderboard"

_METRIC_MAP = {
    "average": "Average ⬆️",
    "ifeval": "IFEval",
    "bbh": "BBH",
    "math_lvl_5": "MATH Lvl 5",
    "gpqa": "GPQA",
    "musr": "MUSR",
    "mmlu_pro": "MMLU-PRO",
}


def _clean_model_name(raw: str) -> str:
    if not raw:
        return ""
    m = re.search(r">([^<]+)</a>", raw)
    return m.group(1).strip() if m else raw.strip()


def _row_to_entry(row: dict[str, Any]) -> LeaderboardEntry | None:
    if row.get("Flagged"):
        return None
    fullname = row.get("fullname") or ""
    if not fullname:
        return None
    display = _clean_model_name(row.get("Model", "")) or fullname
    organization = fullname.split("/", 1)[0] if "/" in fullname else "unknown"
    metrics = {
        key: float(row[col])
        for key, col in _METRIC_MAP.items()
        if isinstance(row.get(col), (int, float))
    }
    return LeaderboardEntry(
        model_id=fullname,
        display_name=display,
        organization=organization,
        source="huggingface",
        metrics=metrics,
        source_url=f"https://huggingface.co/{fullname}",
        extra={
            "params_b": row.get("#Params (B)"),
            "license": row.get("Hub License"),
            "precision": row.get("Precision"),
        },
    )


class HuggingFaceLeaderboard(LeaderboardSource):
    name = "huggingface"
    description = "HuggingFace Open LLM Leaderboard v2 (IFEval, BBH, MATH, GPQA, MUSR, MMLU-PRO)"

    def __init__(self, *, top_n: int = 100) -> None:
        self.top_n = top_n

    def fetch(self) -> LeaderboardSnapshot:
        rows: list[dict[str, Any]] = []
        with httpx.Client(timeout=30) as client:
            offset = 0
            while len(rows) < self.top_n:
                length = min(PAGE_SIZE, self.top_n - len(rows))
                r = client.get(
                    BASE_URL,
                    params={
                        "dataset": DATASET,
                        "config": "default",
                        "split": "train",
                        "offset": offset,
                        "length": length,
                    },
                )
                r.raise_for_status()
                payload = r.json()
                page = payload.get("rows", [])
                if not page:
                    break
                rows.extend(row["row"] for row in page)
                offset += len(page)

        entries = [e for e in (_row_to_entry(r) for r in rows) if e]
        return LeaderboardSnapshot(
            source=self.name,
            source_url=SOURCE_URL,
            entries=entries,
        )
