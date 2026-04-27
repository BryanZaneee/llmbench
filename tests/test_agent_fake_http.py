import pytest

from llmbench.tools.fake_http import FakeHttp, build_fake_http_tools


@pytest.mark.asyncio
async def test_get_hits_registered_route():
    state = FakeHttp()
    state.register("GET", "/users", body=[{"id": 1}, {"id": 2}])
    tools = build_fake_http_tools(state)
    result = await tools["http_get"].run(path="/users")
    assert result == {"status": 200, "body": [{"id": 1}, {"id": 2}]}
    assert len(state.calls) == 1
    assert state.calls[0]["method"] == "GET"
    assert state.calls[0]["path"] == "/users"
    assert state.calls[0]["status"] == 200


@pytest.mark.asyncio
async def test_get_miss_returns_404():
    state = FakeHttp()
    tools = build_fake_http_tools(state)
    result = await tools["http_get"].run(path="/missing")
    assert result["status"] == 404
    assert "error" in result["body"]
    assert len(state.calls) == 1
    assert state.calls[0]["status"] == 404


@pytest.mark.asyncio
async def test_post_hits_registered_route():
    state = FakeHttp()
    state.register("POST", "/audit", body={"ok": True})
    tools = build_fake_http_tools(state)
    request_body = {"action": "login", "user": "alice"}
    result = await tools["http_post"].run(path="/audit", body=request_body)
    assert result == {"status": 200, "body": {"ok": True}}
    assert state.calls[0]["body"] == request_body


@pytest.mark.asyncio
async def test_post_records_body_on_miss():
    state = FakeHttp()
    tools = build_fake_http_tools(state)
    request_body = {"key": "value"}
    result = await tools["http_post"].run(path="/nowhere", body=request_body)
    assert result["status"] == 404
    assert state.calls[0]["body"] == request_body


@pytest.mark.asyncio
async def test_method_case_insensitive():
    state = FakeHttp()
    state.register("get", "/ping", body="pong")
    tools = build_fake_http_tools(state)
    result = await tools["http_get"].run(path="/ping")
    assert result == {"status": 200, "body": "pong"}


@pytest.mark.asyncio
async def test_multiple_calls_accumulate():
    state = FakeHttp()
    state.register("GET", "/a", body=1)
    state.register("GET", "/b", body=2)
    tools = build_fake_http_tools(state)
    await tools["http_get"].run(path="/a")
    await tools["http_get"].run(path="/b")
    await tools["http_get"].run(path="/c")
    assert len(state.calls) == 3
    assert state.calls[0]["path"] == "/a"
    assert state.calls[1]["path"] == "/b"
    assert state.calls[2]["path"] == "/c"


@pytest.mark.asyncio
async def test_build_fake_http_tools_returns_correct_keys():
    state = FakeHttp()
    tools = build_fake_http_tools(state)
    assert set(tools.keys()) == {"http_get", "http_post"}
    assert tools["http_get"]._http is state
    assert tools["http_post"]._http is state
