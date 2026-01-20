"""Functional flow tests for local vector search ingestion and retrieval."""

from __future__ import annotations

from pathlib import Path

from src.config import get_config
from src.dataprep.knowledge_db import KnowledgeDBManager
from src.dataprep.mcp_functions import upload_files_to_vectorstore, vector_search


def _snapshot_config(config):
    return {
        "data": config.data.model_copy(deep=True),
        "vector_search": config.vector_search.model_copy(deep=True),
    }


def _restore_config(config, snapshot):
    config.data = snapshot["data"]
    config.vector_search = snapshot["vector_search"]


def test_upload_and_vector_search_flow(tmp_path):
    config = get_config()
    snapshot = _snapshot_config(config)

    storage_dir = tmp_path / "data"
    storage_dir.mkdir(parents=True, exist_ok=True)
    config.data.local_storage_dir = str(storage_dir)
    config.data.knowledge_db_path = str(tmp_path / "knowledge_db.json")
    config.vector_search.index_name = "test-index"
    config.vector_search.provider = "local"
    config.vector_search.top_k = 3
    config.vector_search.score_threshold = None

    long_padding = " filler" * 300
    content = (
        "Intro section about course logistics.\n"
        f"{long_padding}\n"
        "This section explains the transformer attention mechanism in detail.\n"
        f"{long_padding}\n"
        "Final section on evaluation.\n"
    )

    KnowledgeDBManager._instance = None
    KnowledgeDBManager._url_index = {}
    KnowledgeDBManager._name_index = {}

    source_file = tmp_path / "syllabus.md"
    source_file.write_text(content, encoding="utf-8")

    result = upload_files_to_vectorstore(
        inputs=[str(source_file)], config=config, vectorstore_name=config.vector_search.index_name
    )

    assert result.upload_count == 1
    stored_file = Path(config.data.local_storage_dir) / "syllabus.md"
    assert stored_file.exists()

    db_manager = KnowledgeDBManager(Path(config.data.knowledge_db_path))
    entry = db_manager.find_by_name("syllabus.md")
    assert entry is not None
    assert entry.vector_doc_id is not None

    search_result = vector_search(query="attention mechanism", config=config)

    assert search_result.query == "attention mechanism"
    assert search_result.results
    assert any(
        hit.metadata.get("filename") == "syllabus.md" for hit in search_result.results
    )
    assert all(isinstance(hit.metadata.get("chunk_index"), int) for hit in search_result.results)
    assert any("attention mechanism" in hit.document.lower() for hit in search_result.results)

    _restore_config(config, snapshot)
