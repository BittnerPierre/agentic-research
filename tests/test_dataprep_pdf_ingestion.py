from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from src.config import get_config
from src.dataprep.knowledge_db import KnowledgeDBManager
from src.dataprep.mcp_functions import upload_files_to_vectorstore, vector_search
from src.dataprep.pdf_utils import extract_pdf_text_from_path
from src.dataprep.vector_store_utils import resolve_inputs_to_entries
from src.dataprep.web_loader_improved import fetch_web_content_improved


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


def _setup_local_config(tmp_path):
    config = get_config()
    snapshot = _snapshot_config(config)
    _reset_knowledge_db()

    storage_dir = tmp_path / "data"
    storage_dir.mkdir(parents=True, exist_ok=True)
    config.data.local_storage_dir = str(storage_dir)
    config.data.knowledge_db_path = str(tmp_path / "knowledge_db.json")
    config.vector_search.provider = "local"
    config.vector_search.index_name = "pdf-test-index"
    config.vector_search.chunk_size = 80
    config.vector_search.chunk_overlap = 10
    return config, snapshot


def _build_pdf_bytes(pages: list[str]) -> bytes:
    def _escape(text: str) -> str:
        return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

    objects: list[tuple[int, bytes]] = []
    page_numbers: list[int] = []

    objects.append((1, b"<< /Type /Catalog /Pages 2 0 R >>"))
    objects.append((3, b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"))

    next_obj = 4
    for text in pages:
        page_obj = next_obj
        content_obj = next_obj + 1
        next_obj += 2
        page_numbers.append(page_obj)

        stream = (f"BT\n/F1 12 Tf\n72 720 Td\n({_escape(text)}) Tj\nET\n").encode()
        objects.append(
            (
                content_obj,
                b"<< /Length "
                + str(len(stream)).encode("ascii")
                + b" >>\nstream\n"
                + stream
                + b"endstream",
            )
        )
        objects.append(
            (
                page_obj,
                (
                    f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
                    f"/Resources << /Font << /F1 3 0 R >> >> /Contents {content_obj} 0 R >>"
                ).encode(),
            )
        )

    kids = " ".join(f"{page_num} 0 R" for page_num in page_numbers)
    objects.append((2, f"<< /Type /Pages /Kids [{kids}] /Count {len(page_numbers)} >>".encode()))
    objects.sort(key=lambda item: item[0])

    chunks = [b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"]
    offsets = {0: 0}
    current_offset = len(chunks[0])
    for obj_num, payload in objects:
        offsets[obj_num] = current_offset
        obj_block = f"{obj_num} 0 obj\n".encode("ascii") + payload + b"\nendobj\n"
        chunks.append(obj_block)
        current_offset += len(obj_block)

    xref_offset = current_offset
    max_obj = max(offsets)
    xref_entries = [b"0000000000 65535 f \n"]
    for obj_num in range(1, max_obj + 1):
        xref_entries.append(f"{offsets[obj_num]:010d} 00000 n \n".encode("ascii"))

    chunks.append(f"xref\n0 {max_obj + 1}\n".encode("ascii"))
    chunks.extend(xref_entries)
    chunks.append(
        (
            f"trailer\n<< /Size {max_obj + 1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n"
        ).encode("ascii")
    )
    return b"".join(chunks)


def test_extract_pdf_text_from_path_extracts_text_from_pdf(tmp_path):
    pdf_path = tmp_path / "sample.pdf"
    pdf_path.write_bytes(_build_pdf_bytes(["Alpha page", "Beta page"]))

    content = extract_pdf_text_from_path(pdf_path).text

    assert "## Page 1" in content
    assert "Alpha page" in content
    assert "## Page 2" in content
    assert "Beta page" in content


def test_upload_files_to_vectorstore_indexes_local_pdf(tmp_path):
    config, snapshot = _setup_local_config(tmp_path)

    pdf_path = Path(config.data.local_storage_dir) / "research_note.pdf"
    pdf_path.write_bytes(
        _build_pdf_bytes(
            [
                "Revenue growth and margin expansion in 2025",
                "Cash flow outlook and debt profile remain stable",
            ]
        )
    )

    result = upload_files_to_vectorstore(
        inputs=[str(pdf_path)],
        config=config,
        vectorstore_name="pdf-test-index",
    )
    search = vector_search(query="margin expansion", config=config)

    assert result.upload_count == 1
    assert search.results
    assert any("margin expansion" in hit.document.lower() for hit in search.results)

    db_manager = KnowledgeDBManager(Path(config.data.knowledge_db_path))
    entry = db_manager.find_by_name("research_note.pdf")
    assert entry is not None
    assert entry.normalized_filename == "normalized/research_note.pdf.md"
    assert (Path(config.data.local_storage_dir) / entry.normalized_filename).exists()

    _restore_config(config, snapshot)


def test_fetch_web_content_improved_parses_pdf_response(monkeypatch):
    pdf_bytes = _build_pdf_bytes(["Document fetched over HTTP"])

    class _FakeResponse:
        def __init__(self):
            self.status = 200
            self.headers = {
                "Content-Type": "application/pdf",
                "Content-Encoding": "",
            }

        def read(self):
            return pdf_bytes

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda *_args, **_kwargs: _FakeResponse(),
    )
    monkeypatch.setattr(
        "src.dataprep.web_loader_improved.get_config",
        lambda: SimpleNamespace(debug=SimpleNamespace(enabled=False, output_dir="unused")),
    )

    doc = fetch_web_content_improved("https://example.com/annual-report.pdf")

    assert doc is not None
    assert doc.metadata["title"] == "annual-report pdf"
    assert "Document fetched over HTTP" in doc.page_content


def test_local_pdf_resolution_reuses_normalized_cache_when_source_is_unchanged(
    monkeypatch, tmp_path
):
    config, snapshot = _setup_local_config(tmp_path)
    pdf_path = Path(config.data.local_storage_dir) / "cached.pdf"
    pdf_path.write_bytes(_build_pdf_bytes(["Cached content"]))

    db_manager = KnowledgeDBManager(Path(config.data.knowledge_db_path))
    first = resolve_inputs_to_entries([str(pdf_path)], config, db_manager, pdf_path.parent)
    assert len(first) == 1
    assert first[0].force_reindex is False

    calls = {"count": 0}

    def _fail_if_called(_path):
        calls["count"] += 1
        raise AssertionError("PDF should not be reparsed when unchanged")

    monkeypatch.setattr(
        "src.dataprep.vector_store_utils.extract_pdf_text_from_path",
        _fail_if_called,
    )

    second = resolve_inputs_to_entries([str(pdf_path)], config, db_manager, pdf_path.parent)

    assert len(second) == 1
    assert second[0].force_reindex is False
    assert second[0].file_path.name == "cached.pdf.md"
    assert calls["count"] == 0

    _restore_config(config, snapshot)


def test_local_pdf_resolution_invalidates_cache_when_source_changes(tmp_path):
    config, snapshot = _setup_local_config(tmp_path)
    pdf_path = Path(config.data.local_storage_dir) / "mutable.pdf"
    pdf_path.write_bytes(_build_pdf_bytes(["Version one"]))

    db_manager = KnowledgeDBManager(Path(config.data.knowledge_db_path))
    resolve_inputs_to_entries([str(pdf_path)], config, db_manager, pdf_path.parent)

    pdf_path.write_bytes(_build_pdf_bytes(["Version two updated"]))

    resolved = resolve_inputs_to_entries([str(pdf_path)], config, db_manager, pdf_path.parent)
    assert len(resolved) == 1
    assert resolved[0].force_reindex is True

    artifact_text = resolved[0].file_path.read_text(encoding="utf-8")
    assert "Version two updated" in artifact_text

    _restore_config(config, snapshot)


def test_local_pdf_reupload_replaces_indexed_content_when_source_changes(tmp_path):
    config, snapshot = _setup_local_config(tmp_path)
    pdf_path = Path(config.data.local_storage_dir) / "replaceable.pdf"
    pdf_path.write_bytes(_build_pdf_bytes(["Obsolete phrase only"]))

    first = upload_files_to_vectorstore(
        inputs=[str(pdf_path)],
        config=config,
        vectorstore_name="pdf-test-index",
    )
    assert first.upload_count == 1

    pdf_path.write_bytes(_build_pdf_bytes(["Fresh growth drivers only"]))

    second = upload_files_to_vectorstore(
        inputs=[str(pdf_path)],
        config=config,
        vectorstore_name="pdf-test-index",
    )

    new_search = vector_search(query="growth drivers", config=config)
    old_search = vector_search(query="obsolete phrase", config=config)

    assert second.upload_count == 1
    assert new_search.results
    assert any("growth drivers" in hit.document.lower() for hit in new_search.results)
    assert all("obsolete phrase" not in hit.document.lower() for hit in old_search.results)

    _restore_config(config, snapshot)
