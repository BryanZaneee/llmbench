"""api-orchestration task: fetch users from mock API A, post each to mock API B.

The agent must GET /users, extract each user's id and name, then POST
{user_id, name} to /audit for every user. The field rename (id -> user_id)
forces an actual transform rather than a blind passthrough.
"""

from __future__ import annotations

from ..schema import Budget, VerdictResult
from ..tools.fake_http import FakeHttp, build_fake_http_tools
from .base import Task, TaskCheckResult, TaskSetup, register_task

_USERS = [
    {"id": 1, "name": "Alice", "email": "alice@x.com"},
    {"id": 2, "name": "Bob", "email": "bob@x.com"},
    {"id": 3, "name": "Carol", "email": "carol@x.com"},
]

_EXPECTED_PAIRS: set[tuple[int, str]] = {(u["id"], u["name"]) for u in _USERS}

_SYSTEM = (
    "You are an API integration agent. You have two tools: http_get and http_post. "
    "Follow the user's instructions exactly. Do not add extra requests."
)

_USER_PROMPT = (
    "1. Call http_get with path=\"/users\".\n"
    "2. For each user in the response body, call http_post with path=\"/audit\" "
    "and body {\"user_id\": <user.id>, \"name\": <user.name>}. "
    "Note: use the key \"user_id\" (not \"id\").\n"
    "3. Stop once every user has been posted to /audit."
)


@register_task
class ApiOrchestrationTask(Task):
    id = "api-orchestration"
    version = "1.0.0"
    description = "Fetch a list of users from /users, then POST {user_id, name} for each to /audit."

    def setup(self) -> TaskSetup:
        self.http = FakeHttp()
        self.http.register("GET", "/users", status=200, body=list(_USERS))
        self.http.register("POST", "/audit", status=200, body={"ok": True})
        return TaskSetup(
            system=_SYSTEM,
            user_prompt=_USER_PROMPT,
            tools=build_fake_http_tools(self.http),
            budget=Budget(max_steps=15),
        )

    def check(self) -> TaskCheckResult:
        calls = self.http.calls

        get_calls = [c for c in calls if c["method"] == "GET" and c["path"] == "/users"]
        post_calls = [c for c in calls if c["method"] == "POST" and c["path"] == "/audit"]
        other_calls = [c for c in calls if not (
            (c["method"] == "GET" and c["path"] == "/users") or
            (c["method"] == "POST" and c["path"] == "/audit")
        )]

        if other_calls:
            paths = ", ".join(f"{c['method']} {c['path']}" for c in other_calls)
            return TaskCheckResult(
                verdict=VerdictResult.FAIL,
                detail=f"unexpected requests: {paths}",
            )

        if len(get_calls) != 1:
            return TaskCheckResult(
                verdict=VerdictResult.FAIL,
                detail=f"expected 1 GET /users call, got {len(get_calls)}",
            )

        if len(post_calls) != 3:
            return TaskCheckResult(
                verdict=VerdictResult.FAIL,
                detail=f"expected 3 POST /audit calls, got {len(post_calls)}",
            )

        for call in post_calls:
            body = call.get("body") or {}
            if set(body.keys()) != {"user_id", "name"}:
                return TaskCheckResult(
                    verdict=VerdictResult.FAIL,
                    detail=(
                        f"POST /audit body has wrong keys: {set(body.keys())!r}; "
                        "expected exactly {\"user_id\", \"name\"}"
                    ),
                )

        posted_pairs = {(c["body"]["user_id"], c["body"]["name"]) for c in post_calls}
        if posted_pairs != _EXPECTED_PAIRS:
            missing = _EXPECTED_PAIRS - posted_pairs
            extra = posted_pairs - _EXPECTED_PAIRS
            parts: list[str] = []
            if missing:
                parts.append(f"missing: {missing}")
            if extra:
                parts.append(f"extra: {extra}")
            return TaskCheckResult(
                verdict=VerdictResult.FAIL,
                detail=f"posted (user_id, name) set mismatch; {'; '.join(parts)}",
            )

        return TaskCheckResult(verdict=VerdictResult.PASS)
