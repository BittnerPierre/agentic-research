"""Tests for dataprep download/metadata and late attachment flows."""

from __future__ import annotations

from pathlib import Path

from src.config import get_config
from src.dataprep.knowledge_db import KnowledgeDBManager
from src.dataprep.mcp_functions import (
    download_and_store_url,
    upload_files_to_vectorstore,
    vector_search,
)
from src.dataprep.models import KnowledgeEntry
from src.dataprep.web_loader_improved import WebDocument


class _FakeFilesAPI:
    def __init__(self, created_ids: list[str]):
        self._created_ids = created_ids

    def create(self, file, purpose):
        _ = (file, purpose)
        file_id = f"file_{len(self._created_ids) + 1}"
        self._created_ids.append(file_id)
        return type("UploadResult", (), {"id": file_id})


class _FakeVectorStoreFilesAPI:
    def __init__(self, attached_ids: list[tuple[str, str]]):
        self._attached_ids = attached_ids

    def create(self, vector_store_id: str, file_id: str):
        self._attached_ids.append((vector_store_id, file_id))
        return type("VectorStoreFile", (), {"id": f"vsf_{file_id}", "status": "completed"})


class _FakeVectorStoresAPI:
    def __init__(self, attached_ids: list[tuple[str, str]]):
        self.files = _FakeVectorStoreFilesAPI(attached_ids)


class _FakeOpenAIUpload:
    def __init__(self, created_ids: list[str], attached_ids: list[tuple[str, str]]):
        self.files = _FakeFilesAPI(created_ids)
        self.vector_stores = _FakeVectorStoresAPI(attached_ids)


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


def _setup_config(tmp_path, provider: str):
    config = get_config()
    snapshot = _snapshot_config(config)
    _reset_knowledge_db()

    storage_dir = tmp_path / "data"
    storage_dir.mkdir(parents=True, exist_ok=True)
    config.data.local_storage_dir = str(storage_dir)
    config.data.knowledge_db_path = str(tmp_path / "knowledge_db.json")
    config.vector_search.provider = provider
    config.vector_search.index_name = "test-index"
    return config, snapshot


def test_download_and_store_url_generates_metadata(monkeypatch, tmp_path):
    config, snapshot = _setup_config(tmp_path, provider="local")

    url = "https://example.com/doc"
    doc = WebDocument(content="Test content for metadata.", url=url, title="Doc Title")

    monkeypatch.setattr("src.dataprep.mcp_functions.load_documents_from_urls", lambda _urls: [doc])
    monkeypatch.setattr(
        "src.dataprep.mcp_functions._extract_keywords_with_llm",
        lambda _doc, _config: ["alpha", "beta", "gamma"],
    )
    monkeypatch.setattr(
        "src.dataprep.mcp_functions._extract_summary_with_llm",
        lambda _doc, _config: "Summary text",
    )

    filename = download_and_store_url(url, config)
    stored_file = Path(config.data.local_storage_dir) / filename
    assert stored_file.exists()

    db_manager = KnowledgeDBManager(Path(config.data.knowledge_db_path))
    entry = db_manager.lookup_url(url)
    assert entry is not None
    assert entry.title == "Doc Title"
    assert entry.summary == "Summary text"
    assert "alpha" in entry.keywords

    _restore_config(config, snapshot)


def test_late_attachment_local_flow(monkeypatch, tmp_path):
    config, snapshot = _setup_config(tmp_path, provider="local")

    url = "https://example.com/late-attach"
    doc = WebDocument(
        content="Section on vector retrieval and attachment.", url=url, title="Late Attachment"
    )

    monkeypatch.setattr("src.dataprep.mcp_functions.load_documents_from_urls", lambda _urls: [doc])
    monkeypatch.setattr(
        "src.dataprep.mcp_functions._extract_keywords_with_llm",
        lambda _doc, _config: ["vector", "attachment"],
    )
    monkeypatch.setattr(
        "src.dataprep.mcp_functions._extract_summary_with_llm",
        lambda _doc, _config: "Summary",
    )

    download_and_store_url(url, config)
    upload_files_to_vectorstore(inputs=[url], config=config, vectorstore_name="test-index")

    result = vector_search(query="attachment", config=config)
    assert result.results
    assert any(hit.metadata.get("filename") for hit in result.results)

    _restore_config(config, snapshot)


def test_late_attachment_openai_by_url(monkeypatch, tmp_path):
    config, snapshot = _setup_config(tmp_path, provider="openai")

    url = "https://example.com/openai-late-attach"
    doc = WebDocument(content="OpenAI attachment content.", url=url, title="OpenAI Late")

    monkeypatch.setattr("src.dataprep.mcp_functions.load_documents_from_urls", lambda _urls: [doc])
    monkeypatch.setattr(
        "src.dataprep.mcp_functions._extract_keywords_with_llm",
        lambda _doc, _config: ["openai"],
    )
    monkeypatch.setattr(
        "src.dataprep.mcp_functions._extract_summary_with_llm",
        lambda _doc, _config: "Summary",
    )

    download_and_store_url(url, config)

    created_ids: list[str] = []
    attached_ids: list[tuple[str, str]] = []

    monkeypatch.setattr(
        "src.dataprep.vector_backends.OpenAI",
        lambda: _FakeOpenAIUpload(created_ids, attached_ids),
    )
    monkeypatch.setattr(
        "src.dataprep.vector_store_manager.OpenAI",
        lambda: _FakeOpenAIUpload(created_ids, attached_ids),
    )
    monkeypatch.setattr(
        "src.dataprep.vector_backends.VectorStoreManager.get_or_create_vector_store",
        lambda _self: "vs_123",
    )

    result = upload_files_to_vectorstore(inputs=[url], config=config, vectorstore_name="vs_name")
    assert result.upload_count == 1
    assert created_ids == ["file_1"]
    assert attached_ids == [("vs_123", "file_1")]

    _restore_config(config, snapshot)


def test_late_attachment_chroma_reindexes_missing_collection(monkeypatch, tmp_path):
    config, snapshot = _setup_config(tmp_path, provider="chroma")

    storage_dir = Path(config.data.local_storage_dir)
    filename = "smoke_local_doc.md"
    content = "Smoke test content for late attachment."
    (storage_dir / filename).write_text(content, encoding="utf-8")

    db_manager = KnowledgeDBManager(Path(config.data.knowledge_db_path))
    db_manager.add_entry(
        KnowledgeEntry(
            url="file://smoke_local_doc.md",
            filename=filename,
            keywords=[],
            summary=None,
            title=None,
            content_length=len(content),
            vector_doc_id="doc_smoke_local_doc.md",
        )
    )

    class _FakeCollection:
        def __init__(self):
            self.add_calls: list[dict] = []

        def get(self, **_kwargs):
            return {"ids": []}

        def add(self, ids, documents, metadatas, embeddings):
            self.add_calls.append(
                {
                    "ids": ids,
                    "documents": documents,
                    "metadatas": metadatas,
                    "embeddings": embeddings,
                }
            )

    fake_collection = _FakeCollection()

    monkeypatch.setattr(
        "src.dataprep.vector_backends.ChromaVectorBackend._collection",
        lambda _self, _config, _name: fake_collection,
    )
    monkeypatch.setattr(
        "src.dataprep.vector_backends.get_embedding_function",
        lambda _config: (lambda chunks: [[0.0, 0.0, 0.0] for _ in chunks]),
    )
    monkeypatch.setattr(
        "src.dataprep.vector_backends.chunk_text",
        lambda _content, **_kwargs: [content],
    )

    result = upload_files_to_vectorstore(
        inputs=[filename], config=config, vectorstore_name="test-index"
    )
    assert result.upload_count == 1
    assert result.reuse_count == 0
    assert fake_collection.add_calls

    _restore_config(config, snapshot)
