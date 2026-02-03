"""Tests for Chroma backend embedding flow."""

from __future__ import annotations

from src.config import get_config
from src.dataprep.vector_backends import ChromaVectorBackend


def test_chroma_upload_does_not_send_embeddings(monkeypatch, tmp_path):
    config = get_config()
    config.data.local_storage_dir = str(tmp_path)
    config.data.knowledge_db_path = str(tmp_path / "knowledge_db.json")
    config.vector_search.index_name = "test-collection"

    class _FakeCollection:
        def __init__(self):
            self.add_kwargs = None

        def get(self, *args, **kwargs):
            return {"ids": []}

        def add(self, **kwargs):
            self.add_kwargs = kwargs

    fake_collection = _FakeCollection()

    class _FakeClient:
        def get_or_create_collection(self, name, embedding_function=None):
            return fake_collection

    backend = ChromaVectorBackend()
    monkeypatch.setattr(backend, "_client", lambda _config: _FakeClient())

    test_file = tmp_path / "doc.txt"
    test_file.write_text("Hello world", encoding="utf-8")

    backend.upload_files([str(test_file)], config, "test-collection")

    assert fake_collection.add_kwargs is not None
    assert "embeddings" not in fake_collection.add_kwargs


def test_chroma_search_uses_query_texts(monkeypatch):
    config = get_config()
    config.vector_search.index_name = "test-collection"

    class _FakeCollection:
        def query(self, **kwargs):
            assert "query_texts" in kwargs
            assert "query_embeddings" not in kwargs
            return {"documents": [["doc"]], "metadatas": [[{}]], "distances": [[0.1]]}

    class _FakeClient:
        def get_or_create_collection(self, name, embedding_function=None):
            return _FakeCollection()

    backend = ChromaVectorBackend()
    monkeypatch.setattr(backend, "_client", lambda _config: _FakeClient())

    backend.search("hello", config)
