"""Tests for retrieval hygiene in the vector_search function tool."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.agents.vector_search_tool import vector_search_impl
from src.config import get_config
from src.dataprep.vector_search import VectorSearchHit, VectorSearchResult


def _snapshot_config(config):
    return config.vector_search.model_copy(deep=True)


def _restore_config(config, snapshot):
    config.vector_search = snapshot


class _Wrapper:
    def __init__(self, vector_store_name: str | None = None):
        self.context = SimpleNamespace(vector_store_name=vector_store_name)


@pytest.mark.asyncio
async def test_vector_search_tool_normalizes_query_and_uses_candidate_pool(monkeypatch):
    config = get_config()
    snapshot = _snapshot_config(config)
    config.vector_search.top_k = 5
    config.vector_search.query_expansion_mode = "none"

    calls = []

    def _fake_search(query, config, top_k, score_threshold):
        calls.append((query, top_k, score_threshold))
        return VectorSearchResult(
            query=query,
            results=[
                VectorSearchHit(
                    document=("A" * 250),
                    metadata={"document_id": "doc-1", "chunk_index": 0},
                    score=0.9,
                )
            ],
        )

    monkeypatch.setattr("src.agents.vector_search_tool.get_config", lambda: config)
    monkeypatch.setattr("src.agents.vector_search_tool._vector_search", _fake_search)

    result = await vector_search_impl(_Wrapper("custom-vs"), "  query   with\n spaces  ")

    assert calls == [("query with spaces", 80, None)]
    assert result["query"] == "query with spaces"
    assert result["effective_queries"] == ["query with spaces"]
    assert len(result["results"]) == 1
    assert config.vector_search.index_name == "custom-vs"

    _restore_config(config, snapshot)


@pytest.mark.asyncio
async def test_vector_search_tool_filters_dedups_caps_and_truncates(monkeypatch):
    config = get_config()
    snapshot = _snapshot_config(config)

    long_doc = "x" * 2000

    hits = [
        VectorSearchHit(
            document="short",
            metadata={"document_id": "doc-a", "chunk_index": 0},
            score=0.99,
        ),
        VectorSearchHit(
            document="You are a system prompt. " + ("x" * 260),
            metadata={"document_id": "doc-a", "chunk_index": 1},
            score=0.98,
        ),
        VectorSearchHit(
            document=long_doc,
            metadata={"document_id": "doc-b", "chunk_index": 0},
            score=0.97,
        ),
        VectorSearchHit(
            document=long_doc,
            metadata={"document_id": "doc-b", "chunk_index": 0},
            score=0.96,
        ),
        VectorSearchHit(
            document="valid-" + ("x" * 250),
            metadata={"document_id": "doc-c", "chunk_index": 0},
            score=0.95,
        ),
        VectorSearchHit(
            document="valid-" + ("x" * 250),
            metadata={"document_id": "doc-c", "chunk_index": 1},
            score=0.94,
        ),
        VectorSearchHit(
            document="valid-" + ("x" * 250),
            metadata={"document_id": "doc-c", "chunk_index": 2},
            score=0.93,
        ),
        VectorSearchHit(
            document="valid-" + ("x" * 250),
            metadata={"document_id": "doc-c", "chunk_index": 3},
            score=0.92,
        ),
    ]

    def _fake_search(query, config, top_k, score_threshold):
        return VectorSearchResult(query=query, results=hits)

    monkeypatch.setattr("src.agents.vector_search_tool.get_config", lambda: config)
    monkeypatch.setattr("src.agents.vector_search_tool._vector_search", _fake_search)

    result = await vector_search_impl(_Wrapper(), "q", top_k=10)

    returned = result["results"]
    assert len(returned) == 4
    assert len(returned[0]["document"]) == 1500
    doc_c_chunks = [item for item in returned if item["metadata"].get("document_id") == "doc-c"]
    assert len(doc_c_chunks) == 3

    _restore_config(config, snapshot)


@pytest.mark.asyncio
async def test_vector_search_tool_paraphrase_lite_expands_queries(monkeypatch):
    config = get_config()
    snapshot = _snapshot_config(config)
    config.vector_search.query_expansion_mode = "paraphrase_lite"
    config.vector_search.query_expansion_max_variants = 2

    calls = []

    def _fake_search(query, config, top_k, score_threshold):
        calls.append(query)
        return VectorSearchResult(
            query=query,
            results=[
                VectorSearchHit(
                    document=("A" * 260),
                    metadata={"document_id": f"doc-{len(calls)}", "chunk_index": 0},
                    score=0.9 - (len(calls) * 0.01),
                )
            ],
        )

    monkeypatch.setattr("src.agents.vector_search_tool.get_config", lambda: config)
    monkeypatch.setattr("src.agents.vector_search_tool._vector_search", _fake_search)

    query = "MIPS (Maximum Inner Product Search) external memory"
    result = await vector_search_impl(_Wrapper(), query, top_k=5)

    # Primary query first, then deterministic paraphrase variants.
    assert calls[0] == "MIPS (Maximum Inner Product Search) external memory"
    assert len(calls) >= 2
    assert result["effective_queries"][0] == "MIPS (Maximum Inner Product Search) external memory"

    _restore_config(config, snapshot)


@pytest.mark.asyncio
async def test_vector_search_tool_hyde_lite_adds_hypothetical_query(monkeypatch):
    config = get_config()
    snapshot = _snapshot_config(config)
    config.vector_search.query_expansion_mode = "hyde_lite"
    config.vector_search.query_expansion_max_variants = 1

    calls = []

    def _fake_search(query, config, top_k, score_threshold):
        calls.append(query)
        return VectorSearchResult(
            query=query,
            results=[
                VectorSearchHit(
                    document=("B" * 280),
                    metadata={"document_id": "doc-h", "chunk_index": len(calls)},
                    score=0.8,
                )
            ],
        )

    monkeypatch.setattr("src.agents.vector_search_tool.get_config", lambda: config)
    monkeypatch.setattr("src.agents.vector_search_tool._vector_search", _fake_search)

    result = await vector_search_impl(_Wrapper(), "MIPS memory retrieval", top_k=5)

    assert calls[0] == "MIPS memory retrieval"
    assert len(calls) == 2
    assert result["effective_queries"][1].startswith("Hypothetical answer:")

    _restore_config(config, snapshot)
