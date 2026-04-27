"""multi-step-research task: research a fictional company via 4 search queries, write a synthesis.

The agent must issue four search queries about Llamatech, then synthesize a
/research.md report covering founding, products, challenges, and recent news.
Success requires the file to contain at least one specific fact from each category.
"""

from __future__ import annotations

from ..schema import Budget, VerdictResult
from ..tools.fake_fs import FakeFs, build_fake_fs_tools
from ..tools.fake_search import FakeSearch, build_fake_search_tools
from .base import Task, TaskCheckResult, TaskSetup, register_task

_REGISTERED_QUERIES: list[str] = [
    "Llamatech founding",
    "Llamatech products",
    "Llamatech challenges",
    "Llamatech recent news",
]

_SEARCH_DATA: dict[str, list[dict[str, str]]] = {
    "Llamatech founding": [
        {
            "title": "Llamatech: Origin Story",
            "snippet": "Llamatech was founded in 2019 by Marcus Chen in Portland, Oregon as an AI infrastructure startup.",
            "url": "https://example.com/llamatech-origin",
        },
        {
            "title": "Marcus Chen Launches Llamatech",
            "snippet": "Serial entrepreneur Marcus Chen founded Llamatech in Portland, Oregon after leaving his previous company.",
            "url": "https://example.com/chen-launches-llamatech",
        },
    ],
    "Llamatech products": [
        {
            "title": "Llamatech LlamaCloud Platform Overview",
            "snippet": "Llamatech released LlamaCloud in 2021, a managed platform for deploying large language model pipelines at scale.",
            "url": "https://example.com/llamacloud-overview",
        },
        {
            "title": "LlamaCloud Gains Traction",
            "snippet": "Since its release in 2021, LlamaCloud has grown to serve hundreds of enterprise customers.",
            "url": "https://example.com/llamacloud-growth",
        },
    ],
    "Llamatech challenges": [
        {
            "title": "Llamatech Hit by Supply Chain Issues in 2022",
            "snippet": "Llamatech faced severe supply chain issues in 2022, delaying hardware procurement for its data centers.",
            "url": "https://example.com/llamatech-supply-chain",
        },
        {
            "title": "EU Regulatory Scrutiny for Llamatech",
            "snippet": "EU regulatory scrutiny of Llamatech's data handling practices intensified, requiring significant compliance work.",
            "url": "https://example.com/llamatech-eu-scrutiny",
        },
    ],
    "Llamatech recent news": [
        {
            "title": "Llamatech Closes $50M Series B",
            "snippet": "Llamatech raised $50M Series B in 2024, led by a consortium of growth-stage investors.",
            "url": "https://example.com/llamatech-series-b",
        },
        {
            "title": "Llamatech 2024 Expansion Plans",
            "snippet": "With $50M in new funding secured in 2024, Llamatech plans to expand its engineering team and open offices in Europe.",
            "url": "https://example.com/llamatech-2024-expansion",
        },
    ],
}

_VERDICT_CATEGORIES: dict[str, list[str]] = {
    "founding": ["2019", "marcus chen", "portland"],
    "products": ["llamacloud", "2021"],
    "challenges": ["supply chain", "eu", "regulatory"],
    "news": ["$50m", "series b", "2024"],
}

_SYSTEM = (
    "You are a research agent. You have two tools: `search`, which queries a search "
    "engine and returns results, and `write_file`, which writes to a virtual filesystem. "
    "Use them to gather information and produce a written synthesis."
)

_USER_PROMPT = (
    "Research the company Llamatech by running each of the following four search queries "
    "in order:\n"
    "  1. Llamatech founding\n"
    "  2. Llamatech products\n"
    "  3. Llamatech challenges\n"
    "  4. Llamatech recent news\n\n"
    "Then synthesize a research report covering all four topics: founding, products, "
    "challenges, and recent news. Write the final report to /research.md using "
    "`write_file`. The report must include all four sections and reference at least one "
    "specific fact from each search topic."
)


@register_task
class MultiStepResearchTask(Task):
    id = "multi-step-research"
    version = "1.0.0"
    description = "Research a fictional topic via 4 search queries, then write a synthesis to /research.md."

    def __init__(self) -> None:
        self.search = FakeSearch()
        self.fs = FakeFs()

    def setup(self) -> TaskSetup:
        for query, results in _SEARCH_DATA.items():
            self.search.register(query, results)

        tools = {**build_fake_search_tools(self.search), **build_fake_fs_tools(self.fs)}

        return TaskSetup(
            system=_SYSTEM,
            user_prompt=_USER_PROMPT,
            tools=tools,
            budget=Budget(max_steps=20),
        )

    def check(self) -> TaskCheckResult:
        behavior_flags: list[str] = []

        issued_queries = {c.query for c in self.search.calls}
        registered = set(_REGISTERED_QUERIES)
        if issued_queries - registered:
            behavior_flags.append("unregistered_search_query")

        if "/research.md" not in self.fs.files:
            return TaskCheckResult(
                verdict=VerdictResult.FAIL,
                detail="/research.md not found in filesystem",
                behavior_flags=behavior_flags,
            )

        content = self.fs.files["/research.md"]

        if len(content) < 200:
            return TaskCheckResult(
                verdict=VerdictResult.FAIL,
                detail=f"/research.md too short: {len(content)} chars (minimum 200)",
                behavior_flags=behavior_flags,
            )

        lower = content.lower()
        missing: list[str] = []
        matched: list[str] = []

        for category, keywords in _VERDICT_CATEGORIES.items():
            if any(kw in lower for kw in keywords):
                matched.append(category)
            else:
                missing.append(category)

        if missing:
            return TaskCheckResult(
                verdict=VerdictResult.FAIL,
                detail=f"missing facts for categories: {', '.join(missing)}",
                behavior_flags=behavior_flags,
            )

        return TaskCheckResult(
            verdict=VerdictResult.PASS,
            detail=f"all categories matched: {', '.join(matched)}",
            behavior_flags=behavior_flags,
        )
