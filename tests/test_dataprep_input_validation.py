from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.dataprep.knowledge_db import KnowledgeDBManager
from src.dataprep.models import KnowledgeEntry
from src.dataprep.vector_store_utils import (
    is_openai_file_id,
    resolve_inputs_to_entries,
    validate_filename,
    validate_url,
)


def _reset_db_manager():
    KnowledgeDBManager._instance = None
    KnowledgeDBManager._url_index = {}
    KnowledgeDBManager._name_index = {}
    KnowledgeDBManager._openai_file_id_index = {}


def _make_config(tmp_path):
    return SimpleNamespace(
        data=SimpleNamespace(
            local_storage_dir=str(tmp_path / "storage"),
            knowledge_db_path=tmp_path / "knowledge_db.json",
        )
    )


@pytest.mark.parametrize(
    "url",
    [
        "https://example.com",
        "http://example.com/path?x=1",
    ],
)
def test_validate_url_accepts_valid_urls(url):
    validate_url(url)


@pytest.mark.parametrize(
    "url",
    [
        "ftp://example.com",
        "http://",
        "example.com",
        "https://exämple.com",
        "https://example.com/white space",
    ],
)
def test_validate_url_rejects_invalid_urls(url):
    with pytest.raises(ValueError):
        validate_url(url)


@pytest.mark.parametrize(
    "filename",
    [
        "file.txt",
        "file_name-1.md",
        "report",
    ],
)
def test_validate_filename_accepts_valid_filenames(filename):
    validate_filename(filename)


@pytest.mark.parametrize(
    "filename",
    [
        "../file.txt",
        "dir/file.txt",
        "dir\\file.txt",
        "/abs/path.txt",
        "file name.txt",
        "..",
        ".hidden",
    ],
)
def test_validate_filename_rejects_invalid_filenames(filename):
    with pytest.raises(ValueError):
        validate_filename(filename)


def test_is_openai_file_id():
    assert is_openai_file_id("file-abc123")
    assert is_openai_file_id("file_ABC123")
    assert not is_openai_file_id("file")
    assert not is_openai_file_id("file-")
    assert not is_openai_file_id("not-file-abc")


def test_resolve_inputs_supports_openai_file_id(tmp_path):
    _reset_db_manager()
    config = _make_config(tmp_path)
    local_dir = tmp_path / "storage"
    local_dir.mkdir(parents=True, exist_ok=True)
    (local_dir / "doc.md").write_text("content", encoding="utf-8")

    db_manager = KnowledgeDBManager(config.data.knowledge_db_path)
    entry = KnowledgeEntry(
        url="file://doc.md",
        filename="doc.md",
        keywords=[],
        summary=None,
        openai_file_id="file-abc123",
    )
    db_manager.add_entry(entry)

    resolved = resolve_inputs_to_entries(
        ["file-abc123"],
        config,
        db_manager,
        local_dir,
    )

    assert len(resolved) == 1
    resolved_entry, resolved_path = resolved[0]
    assert resolved_entry.filename == "doc.md"
    assert resolved_path == local_dir / "doc.md"


def test_resolve_inputs_rejects_unknown_file_id(tmp_path):
    _reset_db_manager()
    config = _make_config(tmp_path)
    local_dir = tmp_path / "storage"
    local_dir.mkdir(parents=True, exist_ok=True)
    db_manager = KnowledgeDBManager(config.data.knowledge_db_path)

    with pytest.raises(ValueError):
        resolve_inputs_to_entries(
            ["file-unknown"],
            config,
            db_manager,
            local_dir,
        )
