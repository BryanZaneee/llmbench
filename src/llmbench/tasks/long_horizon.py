"""long-horizon task: read config, fetch three APIs, write a sectioned report.

The agent must parse /config.json to discover sources and the output path, GET
each source API, and produce a markdown report at the configured output_path.
Success requires all four section headings, each team's headcount and highlight,
and the correct total headcount in the Summary section.
"""

from __future__ import annotations

import json

from ..schema import Budget, VerdictResult
from ..tools.fake_fs import FakeFs, build_fake_fs_tools
from ..tools.fake_http import FakeHttp, build_fake_http_tools
from .base import Task, TaskCheckResult, TaskSetup, register_task

_CONFIG_JSON = json.dumps(
    {
        "sources": ["/api/sales", "/api/support", "/api/eng"],
        "output_path": "/report.md",
        "required_sections": ["Sales", "Support", "Engineering", "Summary"],
    },
    indent=2,
)

_SYSTEM = (
    "You are a data-aggregation agent with filesystem and HTTP tools. "
    "Use them to read configuration, fetch remote data, and write structured output. "
    "Be thorough: every required section must appear in the final report."
)

_USER_PROMPT = (
    "Follow these steps exactly:\n"
    "1. Read /config.json to obtain the list of API sources, the output file path, "
    "and the list of required sections.\n"
    "2. For each path listed in `sources`, call http_get with that path and record "
    "the team name, headcount, and highlight from the response body.\n"
    "3. Write a markdown report to the path specified by `output_path`. The report "
    "must contain these sections in order, each introduced by an H2 heading:\n"
    "   ## Sales\n"
    "   ## Support\n"
    "   ## Engineering\n"
    "   ## Summary\n"
    "Each team section (Sales, Support, Engineering) must include the team's "
    "headcount number and their highlight text verbatim.\n"
    "The ## Summary section must include the total headcount (sum of all three teams) "
    "and list each team's highlight as a bullet point.\n"
    "4. When the report is written, stop."
)


class _TrackingFs(FakeFs):
    """FakeFs that records whether delete_file was ever called."""

    def __init__(self, files: dict[str, str]) -> None:
        super().__init__(files=files)
        self.delete_called: bool = False

    def delete(self, path: str) -> None:
        self.delete_called = True
        super().delete(path)


@register_task
class LongHorizonTask(Task):
    id = "long-horizon"
    version = "1.0.0"
    description = (
        "Read /config.json, fetch data from three APIs, write a sectioned report to /report.md."
    )

    def setup(self) -> TaskSetup:
        self.fs = _TrackingFs(files={"/config.json": _CONFIG_JSON})

        self.http = FakeHttp()
        self.http.register(
            "GET",
            "/api/sales",
            status=200,
            body={"team": "Sales", "headcount": 18, "highlight": "closed Q1 enterprise deal"},
        )
        self.http.register(
            "GET",
            "/api/support",
            status=200,
            body={
                "team": "Support",
                "headcount": 12,
                "highlight": "reduced p50 ticket resolution to 4h",
            },
        )
        self.http.register(
            "GET",
            "/api/eng",
            status=200,
            body={"team": "Engineering", "headcount": 34, "highlight": "shipped agentic v1"},
        )

        tools = {**build_fake_fs_tools(self.fs), **build_fake_http_tools(self.http)}

        return TaskSetup(
            system=_SYSTEM,
            user_prompt=_USER_PROMPT,
            tools=tools,
            budget=Budget(max_steps=30),
        )

    def check(self) -> TaskCheckResult:  # noqa: C901 -- flat verdict logic, helpers not worth it
        failures: list[str] = []

        report = self.fs.files.get("/report.md")
        if report is None:
            return TaskCheckResult(
                verdict=VerdictResult.FAIL,
                detail="/report.md not found",
            )

        required_headings = ["## Sales", "## Support", "## Engineering", "## Summary"]
        for heading in required_headings:
            if heading not in report:
                failures.append(f"missing heading: {heading!r}")

        headcounts = [("18", "Sales"), ("12", "Support"), ("34", "Engineering")]
        for number, team in headcounts:
            if number not in report:
                failures.append(f"missing headcount {number} for {team}")

        highlights = [
            "closed Q1 enterprise deal",
            "reduced p50 ticket resolution",
            "shipped agentic v1",
        ]
        lower_report = report.lower()
        for phrase in highlights:
            if phrase.lower() not in lower_report:
                failures.append(f"missing highlight: {phrase!r}")

        summary_start = report.find("## Summary")
        if summary_start != -1:
            summary_section = report[summary_start:]
            if "64" not in summary_section:
                failures.append("missing total headcount 64 in ## Summary")
        else:
            failures.append("missing total headcount 64 in ## Summary (section absent)")

        if failures:
            return TaskCheckResult(
                verdict=VerdictResult.FAIL,
                detail="; ".join(failures),
            )

        behavior_flags: list[str] = []
        if len(self.http.calls) > 5:
            behavior_flags.append("excessive_http_calls")
        if self.fs.delete_called:
            behavior_flags.append("unexpected_delete")

        return TaskCheckResult(
            verdict=VerdictResult.PASS,
            behavior_flags=behavior_flags,
        )
