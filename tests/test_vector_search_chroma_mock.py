"""Mocked tests for the Chroma backend."""

from __future__ import annotations

from src.config import get_config
from src.dataprep.knowledge_db import KnowledgeDBManager
from src.dataprep.mcp_functions import upload_files_to_vectorstore, vector_search


class _FakeCollection:
    def __init__(self):
        self.add_calls = []
        self.query_calls = []
        self.available_filenames = {"syllabus.md"}

    def add(self, **kwargs):
        self.add_calls.append(kwargs)

    def query(self, **kwargs):
        self.query_calls.append(kwargs)
        return {
            "documents": [["chunk-a", "chunk-b"]],
            "metadatas": [[{"filename": "syllabus.md"}, {"filename": "syllabus.md"}]],
            "distances": [[0.1, 0.2]],
        }

    def get(self, where=None, **_kwargs):
        if not where or "filename" not in where:
            return {"ids": []}
        value = where["filename"]
        if isinstance(value, dict) and "$in" in value:
            exists = any(name in self.available_filenames for name in value["$in"])
        else:
            exists = value in self.available_filenames
        return {"ids": ["id-1"]} if exists else {"ids": []}


class _FakeClient:
    def __init__(self):
        self.collections = {}

    def get_or_create_collection(self, name, **_kwargs):
        if name not in self.collections:
            self.collections[name] = _FakeCollection()
        return self.collections[name]


def _snapshot_config(config):
    return {
        "data": config.data.model_copy(deep=True),
        "vector_search": config.vector_search.model_copy(deep=True),
    }


def _restore_config(config, snapshot):
    config.data = snapshot["data"]
    config.vector_search = snapshot["vector_search"]


def _reset_knowledge_db():
    KnowledgeDBManager._instance = None
    KnowledgeDBManager._url_index = {}
    KnowledgeDBManager._name_index = {}


def test_chroma_upload_and_search(monkeypatch, tmp_path):
    config = get_config()
    snapshot = _snapshot_config(config)
    _reset_knowledge_db()

    storage_dir = tmp_path / "data"
    storage_dir.mkdir(parents=True, exist_ok=True)
    config.data.local_storage_dir = str(storage_dir)
    config.data.knowledge_db_path = str(tmp_path / "knowledge_db.json")
    config.vector_search.provider = "chroma"
    config.vector_search.chunk_size = 10
    config.vector_search.chunk_overlap = 0
    config.vector_search.index_name = "test-collection"

    source_file = tmp_path / "syllabus.md"
    source_file.write_text("abcdefghij0123456789", encoding="utf-8")

    client = _FakeClient()

    monkeypatch.setattr(
        "src.dataprep.vector_backends.chromadb.HttpClient",
        lambda **_kwargs: client,
    )

    result = upload_files_to_vectorstore(
        inputs=[str(source_file)], config=config, vectorstore_name="test-collection"
    )

    assert result.upload_count == 1
    collection = client.collections["test-collection"]
    assert collection.add_calls
    add_call = collection.add_calls[0]
    assert "embeddings" not in add_call
    assert len(add_call["documents"]) == 2

    search_result = vector_search(query="query", config=config, top_k=2)
    assert search_result.results

    _restore_config(config, snapshot)


def test_chroma_search_applies_filename_filter(monkeypatch, tmp_path):
    config = get_config()
    snapshot = _snapshot_config(config)
    _reset_knowledge_db()

    storage_dir = tmp_path / "data"
    storage_dir.mkdir(parents=True, exist_ok=True)
    config.data.local_storage_dir = str(storage_dir)
    config.data.knowledge_db_path = str(tmp_path / "knowledge_db.json")
    config.vector_search.provider = "chroma"
    config.vector_search.index_name = "test-collection"

    client = _FakeClient()
    monkeypatch.setattr(
        "src.dataprep.vector_backends.chromadb.HttpClient",
        lambda **_kwargs: client,
    )

    result = vector_search(query="query", config=config, top_k=2, filenames=["syllabus.md"])
    assert result.results

    collection = client.collections["test-collection"]
    assert collection.query_calls
    assert collection.query_calls[-1]["where"] == {"filename": "syllabus.md"}

    _restore_config(config, snapshot)


def test_chroma_search_skips_filter_when_filename_missing(monkeypatch, tmp_path):
    config = get_config()
    snapshot = _snapshot_config(config)
    _reset_knowledge_db()

    storage_dir = tmp_path / "data"
    storage_dir.mkdir(parents=True, exist_ok=True)
    config.data.local_storage_dir = str(storage_dir)
    config.data.knowledge_db_path = str(tmp_path / "knowledge_db.json")
    config.vector_search.provider = "chroma"
    config.vector_search.index_name = "test-collection"

    client = _FakeClient()
    monkeypatch.setattr(
        "src.dataprep.vector_backends.chromadb.HttpClient",
        lambda **_kwargs: client,
    )

    result = vector_search(query="query", config=config, top_k=2, filenames=["missing.md"])
    assert result.results

    collection = client.collections["test-collection"]
    assert collection.query_calls
    assert "where" not in collection.query_calls[-1]

    _restore_config(config, snapshot)
