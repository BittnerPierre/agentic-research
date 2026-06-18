"""Lenient handling for filenames passed to the vector_search function tool."""

from __future__ import annotations

import json

import pytest
from agents.tool_context import ToolContext

from src.agents import vector_search_tool
from src.agents.vector_search_tool import vector_search


def _tool_context() -> ToolContext:
    return ToolContext(
        context=None,
        tool_name="vector_search",
        tool_call_id="test-call",
        tool_arguments="",
    )


@pytest.mark.asyncio
async def test_vector_search_accepts_string_filenames_and_coerces_to_list(monkeypatch):
    captured: dict = {}

    async def _fake_impl(**kwargs):
        captured.update(kwargs)
        return {"hits": []}

    monkeypatch.setattr(vector_search_tool, "vector_search_impl", _fake_impl)

    args = json.dumps({"query": "mips vs rewoo", "filenames": "LLM_Autonomous_Agents.md"})

    await vector_search.on_invoke_tool(_tool_context(), args)

    assert captured.get("filenames") == ["LLM_Autonomous_Agents.md"]
    assert captured.get("query") == "mips vs rewoo"


@pytest.mark.asyncio
async def test_vector_search_still_accepts_list_filenames(monkeypatch):
    captured: dict = {}

    async def _fake_impl(**kwargs):
        captured.update(kwargs)
        return {"hits": []}

    monkeypatch.setattr(vector_search_tool, "vector_search_impl", _fake_impl)

    args = json.dumps({"query": "q", "filenames": ["a.md", "b.md"]})

    await vector_search.on_invoke_tool(_tool_context(), args)

    assert captured.get("filenames") == ["a.md", "b.md"]


@pytest.mark.asyncio
async def test_vector_search_accepts_missing_filenames(monkeypatch):
    captured: dict = {}

    async def _fake_impl(**kwargs):
        captured.update(kwargs)
        return {"hits": []}

    monkeypatch.setattr(vector_search_tool, "vector_search_impl", _fake_impl)

    args = json.dumps({"query": "q"})

    await vector_search.on_invoke_tool(_tool_context(), args)

    assert captured.get("filenames") in (None, [])


@pytest.mark.asyncio
async def test_vector_search_coerces_empty_string_filenames_to_none_or_empty(monkeypatch):
    captured: dict = {}

    async def _fake_impl(**kwargs):
        captured.update(kwargs)
        return {"hits": []}

    monkeypatch.setattr(vector_search_tool, "vector_search_impl", _fake_impl)

    args = json.dumps({"query": "q", "filenames": ""})

    await vector_search.on_invoke_tool(_tool_context(), args)

    assert captured.get("filenames") in (None, [])
