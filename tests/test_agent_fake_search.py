import pytest

from llmbench.tools.fake_search import FakeSearch, build_fake_search_tools

RESULTS_3 = [
    {"title": "A", "snippet": "aa", "url": "https://a.example"},
    {"title": "B", "snippet": "bb", "url": "https://b.example"},
    {"title": "C", "snippet": "cc", "url": "https://c.example"},
]

RESULTS_12 = [
    {"title": str(i), "snippet": f"s{i}", "url": f"https://{i}.example"}
    for i in range(12)
]


@pytest.mark.asyncio
async def test_registered_query_returns_results():
    state = FakeSearch()
    state.register("python async", RESULTS_3)
    tools = build_fake_search_tools(state)
    result = await tools["search"].run(query="python async")
    assert result["query"] == "python async"
    assert result["results"] == RESULTS_3
    assert len(state.calls) == 1
    assert state.calls[0].hit is True
    assert state.calls[0].result_count == 3


@pytest.mark.asyncio
async def test_unregistered_query_returns_empty():
    state = FakeSearch()
    state.register("python async", RESULTS_3)
    tools = build_fake_search_tools(state)
    result = await tools["search"].run(query="something else")
    assert result["query"] == "something else"
    assert result["results"] == []
    assert len(state.calls) == 1
    assert state.calls[0].hit is False
    assert state.calls[0].result_count == 0


@pytest.mark.asyncio
async def test_limit_truncates_results():
    state = FakeSearch()
    state.register("query", RESULTS_12[:5])
    tools = build_fake_search_tools(state)
    result = await tools["search"].run(query="query", limit=2)
    assert len(result["results"]) == 2
    assert state.calls[0].result_count == 2


@pytest.mark.asyncio
async def test_limit_defaults_to_10():
    state = FakeSearch()
    state.register("big query", RESULTS_12)
    tools = build_fake_search_tools(state)
    result = await tools["search"].run(query="big query")
    assert len(result["results"]) == 10
    assert state.calls[0].result_count == 10


@pytest.mark.asyncio
async def test_calls_accumulate_in_order():
    state = FakeSearch()
    state.register("q1", RESULTS_3[:1])
    state.register("q2", RESULTS_3[:2])
    tools = build_fake_search_tools(state)
    await tools["search"].run(query="q1")
    await tools["search"].run(query="q2")
    await tools["search"].run(query="q3")
    assert [c.query for c in state.calls] == ["q1", "q2", "q3"]
    assert state.calls[0].hit is True
    assert state.calls[1].hit is True
    assert state.calls[2].hit is False


def test_build_fake_search_tools_returns_correct_shape():
    state = FakeSearch()
    tools = build_fake_search_tools(state)
    assert set(tools.keys()) == {"search"}
    assert tools["search"].name == "search"
    assert tools["search"]._state is state
