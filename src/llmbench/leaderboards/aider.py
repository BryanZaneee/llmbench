"""Aider Polyglot leaderboard fetcher.

Pulls Aider's polyglot benchmark results from the YAML file the project
maintains in its public repo. Each entry covers an editing benchmark across
multiple programming languages with `pass_rate_1` / `pass_rate_2` (single-
and second-try pass rates) and `percent_cases_well_formed` (edit-format
compliance). The file is small (a few KB) and rarely moves, so a plain
HTTP fetch with PyYAML is enough — no auth, no pagination.
"""

from __future__ import annotations

import re
from typing import Any

import httpx
import yaml

from .base import LeaderboardEntry, LeaderboardSnapshot, LeaderboardSource


YAML_URL = (
    "https://raw.githubusercontent.com/Aider-AI/aider/main/"
    "aider/website/_data/polyglot_leaderboard.yml"
)
SOURCE_URL = "https://aider.chat/docs/leaderboards/"

# Heuristic provider inference from model id. Aider entries don't carry an
# explicit organization field, so we map by prefix/keyword. Anything that
# doesn't match falls through to "unknown".
_ORG_HINTS: list[tuple[str, str]] = [
    ("claude", "anthropic"),
    ("anthropic", "anthropic"),
    ("gpt-", "openai"),
    ("o1", "openai"),
    ("o3", "openai"),
    ("o4", "openai"),
    ("openai", "openai"),
    ("gemini", "google"),
    ("palm", "google"),
    ("llama", "meta"),
    ("meta-", "meta"),
    ("mistral", "mistral"),
    ("mixtral", "mistral"),
    ("codestral", "mistral"),
    ("deepseek", "deepseek"),
    ("qwen", "qwen"),
    ("grok", "xai"),
]


def _organization_for(model: str) -> str:
    m = model.lower()
    for needle, org in _ORG_HINTS:
        if needle in m:
            return org
    return "unknown"


def _row_to_entry(row: dict[str, Any]) -> LeaderboardEntry | None:
    model = row.get("model")
    if not isinstance(model, str) or not model:
        return None

    metrics: dict[str, float] = {}
    p2 = row.get("pass_rate_2")
    if isinstance(p2, (int, float)):
        metrics["polyglot_pass_rate"] = float(p2)
    p1 = row.get("pass_rate_1")
    if isinstance(p1, (int, float)):
        metrics["polyglot_pass_rate_first_try"] = float(p1)
    well_formed = row.get("percent_cases_well_formed")
    if isinstance(well_formed, (int, float)):
        metrics["polyglot_correct_edits"] = float(well_formed)

    if "polyglot_pass_rate" not in metrics:
        return None  # entries without the headline metric aren't useful here

    display = re.sub(r"^anthropic/|^openai/", "", model)

    return LeaderboardEntry(
        model_id=model,
        display_name=display,
        organization=_organization_for(model),
        source="aider",
        metrics=metrics,
        source_url=SOURCE_URL,
        extra={
            "edit_format": row.get("edit_format"),
            "released": row.get("released"),
            "test_cases": row.get("test_cases"),
            "dirname": row.get("dirname"),
        },
    )


class AiderLeaderboard(LeaderboardSource):
    name = "aider"
    description = "Aider Polyglot — multi-language code-editing benchmark (pass rate, edit-format compliance)"

    def fetch(self) -> LeaderboardSnapshot:
        with httpx.Client(timeout=30, follow_redirects=True) as client:
            r = client.get(YAML_URL)
            r.raise_for_status()
            text = r.text

        rows = yaml.safe_load(text) or []
        if not isinstance(rows, list):
            raise RuntimeError("Aider leaderboard YAML is not a list")

        entries: list[LeaderboardEntry] = []
        for row in rows:
            if isinstance(row, dict):
                entry = _row_to_entry(row)
                if entry is not None:
                    entries.append(entry)

        # Rank by headline metric (descending).
        entries.sort(key=lambda e: -e.metrics["polyglot_pass_rate"])
        for i, e in enumerate(entries, 1):
            e.rank = i

        return LeaderboardSnapshot(
            source=self.name,
            source_url=SOURCE_URL,
            entries=entries,
        )
