"""Mocked tests for the OpenAI upload/attach flow."""

from __future__ import annotations

from pathlib import Path

from src.config import get_config
from src.dataprep.knowledge_db import KnowledgeDBManager
from src.dataprep.mcp_functions import upload_files_to_vectorstore


class _FakeFilesAPI:
    def __init__(self, created_ids: list[str]):
        self._created_ids = created_ids

    def create(self, file, purpose):
        _ = (file, purpose)
        file_id = f"file_{len(self._created_ids) + 1}"
        self._created_ids.append(file_id)
        return type("UploadResult", (), {"id": file_id})


class _FakeVectorStoreFilesAPI:
    def __init__(self, attached_ids: list[str]):
        self._attached_ids = attached_ids

    def create(self, vector_store_id: str, file_id: str):
        self._attached_ids.append((vector_store_id, file_id))
        return type("VectorStoreFile", (), {"id": f"vsf_{file_id}", "status": "completed"})


class _FakeVectorStoresAPI:
    def __init__(self, attached_ids: list[str]):
        self.files = _FakeVectorStoreFilesAPI(attached_ids)


class _FakeOpenAI:
    def __init__(self, created_ids: list[str], attached_ids: list[str]):
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


def test_openai_upload_flow_updates_knowledge_db(monkeypatch, tmp_path):
    config = get_config()
    snapshot = _snapshot_config(config)
    _reset_knowledge_db()

    storage_dir = tmp_path / "data"
    storage_dir.mkdir(parents=True, exist_ok=True)
    config.data.local_storage_dir = str(storage_dir)
    config.data.knowledge_db_path = str(tmp_path / "knowledge_db.json")
    config.vector_search.provider = "openai"

    source_file = tmp_path / "syllabus.md"
    source_file.write_text("Simple syllabus content", encoding="utf-8")

    created_ids: list[str] = []
    attached_ids: list[tuple[str, str]] = []

    def _fake_openai():
        return _FakeOpenAI(created_ids, attached_ids)

    monkeypatch.setattr("src.dataprep.vector_backends.OpenAI", _fake_openai)
    monkeypatch.setattr(
        "src.dataprep.vector_backends.VectorStoreManager.get_or_create_vector_store",
        lambda _self: "vs_123",
    )

    result = upload_files_to_vectorstore(
        inputs=[str(source_file)], config=config, vectorstore_name="vs_name"
    )

    assert result.vectorstore_id == "vs_123"
    assert result.upload_count == 1
    assert created_ids == ["file_1"]
    assert attached_ids == [("vs_123", "file_1")]

    db_manager = KnowledgeDBManager(Path(config.data.knowledge_db_path))
    entry = db_manager.find_by_name("syllabus.md")
    assert entry is not None
    assert entry.openai_file_id == "file_1"

    _restore_config(config, snapshot)


def test_openai_upload_flow_reuses_existing_file(monkeypatch, tmp_path):
    config = get_config()
    snapshot = _snapshot_config(config)
    _reset_knowledge_db()

    storage_dir = tmp_path / "data"
    storage_dir.mkdir(parents=True, exist_ok=True)
    config.data.local_storage_dir = str(storage_dir)
    config.data.knowledge_db_path = str(tmp_path / "knowledge_db.json")
    config.vector_search.provider = "openai"

    source_file = tmp_path / "syllabus.md"
    source_file.write_text("Reusable content", encoding="utf-8")

    created_ids: list[str] = []
    attached_ids: list[tuple[str, str]] = []

    def _fake_openai():
        return _FakeOpenAI(created_ids, attached_ids)

    monkeypatch.setattr("src.dataprep.vector_backends.OpenAI", _fake_openai)
    monkeypatch.setattr(
        "src.dataprep.vector_backends.VectorStoreManager.get_or_create_vector_store",
        lambda _self: "vs_123",
    )

    upload_files_to_vectorstore(
        inputs=[str(source_file)], config=config, vectorstore_name="vs_name"
    )

    created_ids.clear()
    attached_ids.clear()

    def _fake_openai_fail():
        client = _FakeOpenAI(created_ids, attached_ids)
        client.files.create = lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("files.create should not be called on reuse")
        )
        return client

    monkeypatch.setattr("src.dataprep.vector_backends.OpenAI", _fake_openai_fail)

    result = upload_files_to_vectorstore(
        inputs=[str(source_file)], config=config, vectorstore_name="vs_name"
    )

    assert result.upload_count == 0
    assert result.reuse_count == 1
    assert attached_ids == [("vs_123", "file_1")]

    _restore_config(config, snapshot)
