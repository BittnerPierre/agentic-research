"""Behavioral tests for the vector_search tool."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from src.config import get_config
from src.dataprep.mcp_functions import vector_search
from src.dataprep.vector_search import VectorSearchHit


@dataclass
class FakeBackend:
    hits: list[VectorSearchHit]
    calls: list[tuple[str, int, float | None]]

    def query(self, query: str, top_k: int, score_threshold: float | None):
        self.calls.append((query, top_k, score_threshold))
        return self.hits


def _snapshot_vector_search_config(config):
    return config.vector_search.model_copy(deep=True)


def _restore_vector_search_config(config, snapshot):
    config.vector_search = snapshot


def test_vector_search_respects_configured_defaults(monkeypatch):
    config = get_config()
    snapshot = _snapshot_vector_search_config(config)
    config.vector_search.top_k = 2
    config.vector_search.score_threshold = 0.4

    backend = FakeBackend(
        hits=[
            VectorSearchHit(document="doc-a", metadata={"filename": "a.md"}, score=0.95),
            VectorSearchHit(document="doc-b", metadata={"filename": "b.md"}, score=0.5),
            VectorSearchHit(document="doc-c", metadata={"filename": "c.md"}, score=0.2),
        ],
        calls=[],
    )

    def _fake_backend_provider(_config):
        return backend

    monkeypatch.setattr(
        "src.dataprep.vector_search.get_vector_search_backend",
        _fake_backend_provider,
    )

    result = vector_search(query="agentic research", config=config)

    assert backend.calls == [("agentic research", 2, 0.4)]
    assert result.query == "agentic research"
    assert [item.metadata["filename"] for item in result.results] == ["a.md", "b.md"]

    _restore_vector_search_config(config, snapshot)


def test_vector_search_allows_overrides(monkeypatch):
    config = get_config()
    snapshot = _snapshot_vector_search_config(config)
    config.vector_search.top_k = 5
    config.vector_search.score_threshold = None

    backend = FakeBackend(
        hits=[
            VectorSearchHit(document="doc-a", metadata={"filename": "a.md"}, score=0.8),
            VectorSearchHit(document="doc-b", metadata={"filename": "b.md"}, score=0.7),
        ],
        calls=[],
    )

    def _fake_backend_provider(_config):
        return backend

    monkeypatch.setattr(
        "src.dataprep.vector_search.get_vector_search_backend",
        _fake_backend_provider,
    )

    result = vector_search(query="vector tool", config=config, top_k=1, score_threshold=0.75)

    assert backend.calls == [("vector tool", 1, 0.75)]
    assert result.query == "vector tool"
    assert [item.metadata["filename"] for item in result.results] == ["a.md"]

    _restore_vector_search_config(config, snapshot)


def test_vector_search_empty_results(monkeypatch):
    config = get_config()
    snapshot = _snapshot_vector_search_config(config)
    config.vector_search.top_k = 3

    backend = FakeBackend(hits=[], calls=[])

    def _fake_backend_provider(_config):
        return backend

    monkeypatch.setattr(
        "src.dataprep.vector_search.get_vector_search_backend",
        _fake_backend_provider,
    )

    result = vector_search(query="no matches", config=config)

    assert backend.calls == [("no matches", 3, None)]
    assert result.query == "no matches"
    assert result.results == []

    _restore_vector_search_config(config, snapshot)
