"""Tests for filename filtering in the local vector search backend."""

from __future__ import annotations

from pathlib import Path

from src.dataprep.vector_search import LocalVectorSearchBackend, create_document


def _build_backend(tmp_path: Path) -> LocalVectorSearchBackend:
    index_path = tmp_path / "vector_index.json"
    return LocalVectorSearchBackend(index_path=index_path, chunk_size=80, chunk_overlap=0)


def test_local_vector_search_filters_by_filename(tmp_path: Path):
    backend = _build_backend(tmp_path)
    docs = [
        create_document(
            content="alpha beta gamma",
            metadata={"filename": "a.md"},
        ),
        create_document(
            content="alpha delta epsilon",
            metadata={"filename": "b.md"},
        ),
    ]
    backend.add_documents(docs)

    hits = backend.query(query="alpha", top_k=5, score_threshold=None, filenames=["a.md"])

    assert hits
    assert {hit.metadata["filename"] for hit in hits} == {"a.md"}


def test_local_vector_search_falls_back_when_filename_missing(tmp_path: Path):
    backend = _build_backend(tmp_path)
    docs = [
        create_document(
            content="alpha beta gamma",
            metadata={"filename": "a.md"},
        ),
        create_document(
            content="alpha delta epsilon",
            metadata={"filename": "b.md"},
        ),
    ]
    backend.add_documents(docs)

    hits = backend.query(query="alpha", top_k=5, score_threshold=None, filenames=["missing.md"])

    assert hits
    assert {hit.metadata["filename"] for hit in hits} <= {"a.md", "b.md"}
