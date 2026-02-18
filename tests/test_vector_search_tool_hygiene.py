"""Tests for retrieval hygiene in the vector_search function tool."""

from __future__ import annotations

import logging
from types import SimpleNamespace

import pytest

from src.agents.vector_search_tool import vector_search_impl
from src.config import get_config
from src.dataprep.vector_search import VectorSearchHit, VectorSearchResult


def _snapshot_config(config):
    return {
        "vector_search": config.vector_search.model_copy(deep=True),
        "agents": config.agents.model_copy(deep=True),
        "vector_store": config.vector_store.model_copy(deep=True),
    }


def _restore_config(config, snapshot):
    config.vector_search = snapshot["vector_search"]
    config.agents = snapshot["agents"]
    config.vector_store = snapshot["vector_store"]


class _Wrapper:
    def __init__(
        self,
        vector_store_name: str | None = None,
        vector_store_id: str | None = None,
    ):
        self.context = SimpleNamespace(
            vector_store_name=vector_store_name, vector_store_id=vector_store_id
        )


@pytest.mark.asyncio
async def test_vector_search_tool_normalizes_query_and_uses_candidate_pool(monkeypatch):
    config = get_config()
    snapshot = _snapshot_config(config)
    config.vector_search.top_k = 5
    config.agents.file_search_rewrite_mode = "none"
    config.agents.file_search_top_k = None
    config.agents.file_search_score_threshold = None

    calls = []

    def _fake_search(query, config, top_k, score_threshold, filenames=None, vectorstore_id=None):
        calls.append((query, top_k, score_threshold, filenames, vectorstore_id))
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

    result = await vector_search_impl(_Wrapper("custom-vs", "vs_123"), "  query   with\n spaces  ")

    assert calls == [("query with spaces", 50, None, [], "vs_123")]
    assert result["query"] == "query with spaces"
    assert result["effective_queries"] == ["query with spaces"]
    assert result["observability"] == {
        "rewrite_requested": False,
        "rewrite_applied": False,
        "rewrite_mode": "none",
        "rewrite_input_query": "query with spaces",
        "effective_queries_count": 1,
        "rewrite_backend": "none_or_fallback",
        "rewrite_domain_hint": "general research",
        "rewrite_domain_hint_source": "heuristic",
        "top_k": 5,
        "score_threshold": None,
        "filenames": None,
    }
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

    def _fake_search(query, config, top_k, score_threshold, filenames=None, vectorstore_id=None):
        return VectorSearchResult(query=query, results=hits)

    monkeypatch.setattr("src.agents.vector_search_tool.get_config", lambda: config)
    monkeypatch.setattr("src.agents.vector_search_tool._vector_search", _fake_search)

    config.agents.file_search_top_k = 10
    result = await vector_search_impl(_Wrapper(), "q")

    returned = result["results"]
    assert len(returned) == 5
    assert len(returned[0]["document"]) == 1500
    doc_c_chunks = [item for item in returned if item["metadata"].get("document_id") == "doc-c"]
    assert len(doc_c_chunks) == 4

    _restore_config(config, snapshot)


@pytest.mark.asyncio
async def test_vector_search_tool_paraphrase_lite_expands_queries(monkeypatch):
    config = get_config()
    snapshot = _snapshot_config(config)
    config.agents.file_search_rewrite_mode = "paraphrase_lite"
    config.agents.file_search_rewrite_max_variants = 2

    calls = []

    def _fake_search(query, config, top_k, score_threshold, filenames=None, vectorstore_id=None):
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
    monkeypatch.setattr(
        "src.agents.vector_search_tool._build_llm_rewrite_queries",
        lambda query, mode, max_variants, config, domain_hint=None: [
            "MIPS Maximum Inner Product Search external memory",
            "MIPS external memory implementation tradeoffs",
        ],
    )

    query = "MIPS (Maximum Inner Product Search) external memory"
    result = await vector_search_impl(
        _Wrapper(),
        query,
    )

    # Primary query first, then deterministic paraphrase variants.
    assert calls[0] == "MIPS (Maximum Inner Product Search) external memory"
    assert len(calls) >= 2
    assert result["effective_queries"][0] == "MIPS (Maximum Inner Product Search) external memory"
    assert result["observability"]["rewrite_requested"] is True
    assert result["observability"]["rewrite_applied"] is True
    assert result["observability"]["rewrite_mode"] == "paraphrase_lite"
    assert result["observability"]["effective_queries_count"] == len(result["effective_queries"])
    assert result["observability"]["rewrite_backend"] == "llm_openai_compatible"
    assert result["observability"]["rewrite_domain_hint"] == "general research"
    assert result["observability"]["rewrite_domain_hint_source"] == "heuristic"

    _restore_config(config, snapshot)


@pytest.mark.asyncio
async def test_vector_search_tool_hyde_lite_adds_hypothetical_query(monkeypatch):
    config = get_config()
    snapshot = _snapshot_config(config)
    config.agents.file_search_rewrite_mode = "hyde_lite"
    config.agents.file_search_rewrite_max_variants = 1

    calls = []

    def _fake_search(query, config, top_k, score_threshold, filenames=None, vectorstore_id=None):
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
    monkeypatch.setattr(
        "src.agents.vector_search_tool._build_llm_rewrite_queries",
        lambda query, mode, max_variants, config, domain_hint=None: [
            "A hypothetical answer about MIPS memory retrieval in autonomous agents"
        ],
    )

    result = await vector_search_impl(
        _Wrapper(),
        "MIPS memory retrieval",
    )

    assert calls[0] == "MIPS memory retrieval"
    assert len(calls) == 2
    assert not result["effective_queries"][1].startswith("Hypothetical answer:")
    assert result["observability"]["rewrite_requested"] is True
    assert result["observability"]["rewrite_applied"] is True
    assert result["observability"]["rewrite_mode"] == "hyde_lite"
    assert result["observability"]["rewrite_input_query"] == "MIPS memory retrieval"
    assert result["observability"]["rewrite_backend"] == "llm_openai_compatible"
    assert result["observability"]["rewrite_domain_hint"] == "general research"
    assert result["observability"]["rewrite_domain_hint_source"] == "heuristic"

    _restore_config(config, snapshot)


@pytest.mark.asyncio
async def test_vector_search_tool_hyde_lite_normalizes_question_like_rewrites(monkeypatch):
    config = get_config()
    snapshot = _snapshot_config(config)
    config.agents.file_search_rewrite_mode = "hyde_lite"
    config.agents.file_search_rewrite_max_variants = 2

    calls = []

    def _fake_search(query, config, top_k, score_threshold, filenames=None, vectorstore_id=None):
        calls.append(query)
        return VectorSearchResult(
            query=query,
            results=[
                VectorSearchHit(
                    document=("D" * 280),
                    metadata={"document_id": f"doc-q-{len(calls)}", "chunk_index": len(calls)},
                    score=0.7,
                )
            ],
        )

    monkeypatch.setattr("src.agents.vector_search_tool.get_config", lambda: config)
    monkeypatch.setattr("src.agents.vector_search_tool._vector_search", _fake_search)
    monkeypatch.setattr(
        "src.agents.vector_search_tool._build_llm_rewrite_queries",
        lambda query, mode, max_variants, config, domain_hint=None: [
            "What are the benefits of Chain-of-Thought prompting in AI models?",
            "How does Chain-of-Thought prompting improve reasoning in AI systems?",
        ],
    )

    result = await vector_search_impl(_Wrapper(), "Chain-of-Thought prompting in AI")

    assert len(result["effective_queries"]) == 2
    assert not result["effective_queries"][1].startswith("Hypothetical answer:")
    assert "?" not in result["effective_queries"][1]

    _restore_config(config, snapshot)


@pytest.mark.asyncio
async def test_vector_search_tool_uses_agent_threshold_from_config(monkeypatch):
    config = get_config()
    snapshot = _snapshot_config(config)
    config.agents.file_search_rewrite_mode = "none"
    config.agents.file_search_top_k = 3
    config.agents.file_search_score_threshold = 0.77

    calls = []

    def _fake_search(query, config, top_k, score_threshold, filenames=None, vectorstore_id=None):
        calls.append((query, top_k, score_threshold, filenames, vectorstore_id))
        return VectorSearchResult(
            query=query,
            results=[
                VectorSearchHit(
                    document=("C" * 260),
                    metadata={"document_id": "doc-t", "chunk_index": 0},
                    score=0.9,
                )
            ],
        )

    monkeypatch.setattr("src.agents.vector_search_tool.get_config", lambda: config)
    monkeypatch.setattr("src.agents.vector_search_tool._vector_search", _fake_search)

    result = await vector_search_impl(_Wrapper(), "threshold test")

    assert calls == [("threshold test", 50, 0.77, [], None)]
    assert result["observability"]["top_k"] == 3
    assert result["observability"]["score_threshold"] == 0.77

    _restore_config(config, snapshot)


@pytest.mark.asyncio
async def test_vector_search_tool_passes_vector_store_id(monkeypatch):
    config = get_config()
    snapshot = _snapshot_config(config)
    config.agents.file_search_rewrite_mode = "none"

    calls = []

    def _fake_search(query, config, top_k, score_threshold, filenames=None, vectorstore_id=None):
        calls.append(vectorstore_id)
        return VectorSearchResult(query=query, results=[])

    monkeypatch.setattr("src.agents.vector_search_tool.get_config", lambda: config)
    monkeypatch.setattr("src.agents.vector_search_tool._vector_search", _fake_search)

    await vector_search_impl(_Wrapper(vector_store_id="vs_abc"), "id test")

    assert calls == ["vs_abc"]

    _restore_config(config, snapshot)


@pytest.mark.asyncio
async def test_vector_search_tool_detects_financial_domain_hint(monkeypatch):
    config = get_config()
    snapshot = _snapshot_config(config)
    config.agents.file_search_rewrite_mode = "none"

    def _fake_search(query, config, top_k, score_threshold, filenames=None, vectorstore_id=None):
        return VectorSearchResult(
            query=query,
            results=[
                VectorSearchHit(
                    document=("E" * 260),
                    metadata={"document_id": "doc-fin", "chunk_index": 0},
                    score=0.9,
                )
            ],
        )

    monkeypatch.setattr("src.agents.vector_search_tool.get_config", lambda: config)
    monkeypatch.setattr("src.agents.vector_search_tool._vector_search", _fake_search)

    result = await vector_search_impl(_Wrapper(), "10-K annual report revenue guidance and EBITDA")

    assert result["observability"]["rewrite_domain_hint"] == "financial research"
    assert result["observability"]["rewrite_domain_hint_source"] == "heuristic"

    _restore_config(config, snapshot)


@pytest.mark.asyncio
async def test_vector_search_tool_caps_openai_retrieve_top_k(monkeypatch):
    config = get_config()
    snapshot = _snapshot_config(config)
    config.vector_search.provider = "openai"
    config.agents.file_search_rewrite_mode = "none"
    config.agents.file_search_top_k = None
    config.agents.file_search_score_threshold = None

    calls = []

    def _fake_search(query, config, top_k, score_threshold, filenames=None, vectorstore_id=None):
        calls.append(top_k)
        return VectorSearchResult(query=query, results=[])

    monkeypatch.setattr("src.agents.vector_search_tool.get_config", lambda: config)
    monkeypatch.setattr("src.agents.vector_search_tool._vector_search", _fake_search)

    await vector_search_impl(_Wrapper(), "cap test")

    assert calls == [50]

    _restore_config(config, snapshot)


@pytest.mark.asyncio
async def test_vector_search_tool_uses_agent_domain_hint_override(monkeypatch):
    config = get_config()
    snapshot = _snapshot_config(config)
    config.agents.file_search_rewrite_mode = "none"

    def _fake_search(query, config, top_k, score_threshold, filenames=None, vectorstore_id=None):
        return VectorSearchResult(
            query=query,
            results=[
                VectorSearchHit(
                    document=("F" * 260),
                    metadata={"document_id": "doc-override", "chunk_index": 0},
                    score=0.9,
                )
            ],
        )

    monkeypatch.setattr("src.agents.vector_search_tool.get_config", lambda: config)
    monkeypatch.setattr("src.agents.vector_search_tool._vector_search", _fake_search)

    result = await vector_search_impl(
        _Wrapper(), "generic prompt engineering topic", domain_hint="financial research"
    )

    assert result["observability"]["rewrite_domain_hint"] == "financial research"
    assert result["observability"]["rewrite_domain_hint_source"] == "agent_override"

    _restore_config(config, snapshot)


@pytest.mark.asyncio
async def test_vector_search_tool_logs_observability_diagnostics(monkeypatch, caplog):
    config = get_config()
    snapshot = _snapshot_config(config)
    config.agents.file_search_rewrite_mode = "none"

    def _fake_search(query, config, top_k, score_threshold, filenames=None, vectorstore_id=None):
        return VectorSearchResult(
            query=query,
            results=[
                VectorSearchHit(
                    document=("G" * 260),
                    metadata={"document_id": "doc-log", "chunk_index": 0},
                    score=0.91,
                )
            ],
        )

    monkeypatch.setattr("src.agents.vector_search_tool.get_config", lambda: config)
    monkeypatch.setattr("src.agents.vector_search_tool._vector_search", _fake_search)

    caplog.set_level(logging.DEBUG, logger="src.agents.vector_search_tool")
    await vector_search_impl(_Wrapper(), "observability query")

    assert "vector_search diagnostics" in caplog.text
    assert "effective_queries" in caplog.text

    _restore_config(config, snapshot)
