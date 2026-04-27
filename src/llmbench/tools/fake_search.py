"""Canned search tool primitive.

Exposes a single `search` Tool instance backed by a FakeSearch state object.
Tasks pre-register query->results entries at setup() time; the model issues
queries and receives the canned results. Unregistered queries return an empty
result list rather than an error, because an empty SERP is a valid real outcome.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .base import Tool


@dataclass
class SearchCall:
    query: str
    hit: bool
    result_count: int


@dataclass
class FakeSearch:
    _table: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    calls: list[SearchCall] = field(default_factory=list)

    def register(self, query: str, results: list[dict[str, Any]]) -> None:
        self._table[query] = results

    def record_call(self, query: str, hit: bool, result_count: int) -> None:
        self.calls.append(SearchCall(query=query, hit=hit, result_count=result_count))

    def lookup(self, query: str) -> list[dict[str, Any]] | None:
        return self._table.get(query)


class SearchTool(Tool):
    name = "search"
    description = (
        "Search and return ranked results. "
        "Returns {query, results: list of {title, snippet, url}}."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "The search query string."},
            "limit": {
                "type": "integer",
                "description": "Maximum number of results to return.",
                "default": 10,
            },
        },
        "required": ["query"],
    }

    def __init__(self, state: FakeSearch) -> None:
        self._state = state

    async def run(self, *, query: str, limit: int = 10) -> dict[str, Any]:
        results = self._state.lookup(query)
        hit = results is not None
        if not hit:
            results = []
        truncated = results[:limit]
        self._state.record_call(query=query, hit=hit, result_count=len(truncated))
        return {"query": query, "results": truncated}


def build_fake_search_tools(state: FakeSearch) -> dict[str, Tool]:
    """Construct the canonical fake_search tool set bound to a single FakeSearch."""
    t = SearchTool(state)
    return {t.name: t}
