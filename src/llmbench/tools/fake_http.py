"""In-memory HTTP tool primitive.

Exposes `http_get` and `http_post` as two Tool instances that share a single
route table (FakeHttp). Tasks register routes at setup() time; verdicts inspect
the `calls` list on the same FakeHttp to see what the model actually requested.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .base import Tool


@dataclass
class FakeHttp:
    _routes: dict[tuple[str, str], tuple[int, Any]] = field(default_factory=dict)
    calls: list[dict[str, Any]] = field(default_factory=list)

    def register(self, method: str, path: str, *, status: int = 200, body: Any = None) -> None:
        self._routes[(method.upper(), path)] = (status, body)

    def record_call(self, method: str, path: str, body: dict | None) -> tuple[int, Any]:
        key = (method.upper(), path)
        if key in self._routes:
            status, response = self._routes[key]
        else:
            status = 404
            response = {"error": f"no route for {method.upper()} {path}"}
        self.calls.append({"method": method.upper(), "path": path, "body": body, "status": status, "response": response})
        return status, response


class HttpGetTool(Tool):
    name = "http_get"
    description = "Make a GET request to a URL and return the JSON response. Returns {status, body}."
    input_schema = {
        "type": "object",
        "properties": {"path": {"type": "string", "description": "URL path to request."}},
        "required": ["path"],
    }

    def __init__(self, http: FakeHttp):
        self._http = http

    async def run(self, *, path: str) -> dict[str, Any]:
        status, body = self._http.record_call("GET", path, None)
        return {"status": status, "body": body}


class HttpPostTool(Tool):
    name = "http_post"
    description = "Make a POST request to a URL with a JSON body and return the JSON response."
    input_schema = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "URL path to request."},
            "body": {"type": "object", "description": "JSON request body."},
        },
        "required": ["path", "body"],
    }

    def __init__(self, http: FakeHttp):
        self._http = http

    async def run(self, *, path: str, body: dict) -> dict[str, Any]:
        status, response = self._http.record_call("POST", path, body)
        return {"status": status, "body": response}


def build_fake_http_tools(state: FakeHttp) -> dict[str, Tool]:
    """Construct the canonical fake_http tool set bound to a single FakeHttp."""
    return {t.name: t for t in (HttpGetTool(state), HttpPostTool(state))}
