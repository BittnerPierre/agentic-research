from __future__ import annotations

import hashlib
import json
from pathlib import Path

import yaml

from evaluations.chunk_snapshot import (
    ChunkSnapshot,
    RetrievedChunk,
    source_chunk_map,
    validate_chunk_snapshot,
)


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _exercise_with_source(tmp_path: Path) -> tuple[Path, str]:
    exercise = tmp_path / "exercise"
    corpus = exercise / "corpus"
    corpus.mkdir(parents=True)
    raw = "---\ntitle: Agents\n---\n# Agents\n\nA grounded raw passage about agent tools.\n"
    (corpus / "Agents_1.md").write_text(raw, encoding="utf-8")
    (exercise / "source_manifest.yaml").write_text(
        yaml.safe_dump(
            {
                "sources": [
                    {
                        "url": "https://example.test/agents",
                        "file_pattern": "Agents*.md",
                        "sha256": _sha256(raw),
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    return exercise, "A grounded raw passage about agent tools."


def _chunk(text: str, *, chunk_id: str = "abcdef12-3456:0") -> RetrievedChunk:
    document_id, chunk_index = chunk_id.rsplit(":", 1)
    return RetrievedChunk(
        chunk_id=chunk_id,
        document_id=document_id,
        chunk_index=int(chunk_index),
        filename="Agents_1.md",
        source="https://example.test/agents",
        text=text,
        sha256=_sha256(text),
        resolved=True,
    )


def test_chunk_snapshot_accepts_content_from_hash_pinned_source(tmp_path: Path) -> None:
    exercise, text = _exercise_with_source(tmp_path)
    snapshot = ChunkSnapshot(schema_version=1, chunks=[_chunk(text)])

    result = validate_chunk_snapshot(snapshot, exercise, tmp_path / "runs" / "run")

    assert result.passed is True
    assert list(result.valid_chunks) == ["abcdef12-3456:0"]


def test_chunk_snapshot_accepts_generated_files_json_manifest(tmp_path: Path) -> None:
    exercise, text = _exercise_with_source(tmp_path)
    (exercise / "source_manifest.yaml").unlink()
    source_path = exercise / "corpus" / "Agents_1.md"
    (exercise / "corpus" / "manifest.json").write_text(
        json.dumps({"generated_files": {source_path.name: _sha256(source_path.read_text())}}),
        encoding="utf-8",
    )

    result = validate_chunk_snapshot(
        ChunkSnapshot(schema_version=1, chunks=[_chunk(text)]),
        exercise,
        tmp_path / "runs" / "run",
    )

    assert result.passed is True
    assert list(result.valid_chunks) == ["abcdef12-3456:0"]


def test_chunk_snapshot_rejects_generated_summary_disguised_as_raw_chunk(
    tmp_path: Path,
) -> None:
    exercise, _ = _exercise_with_source(tmp_path)
    fake_summary = "The source recommends a framework that the raw article never mentions."
    snapshot = ChunkSnapshot(schema_version=1, chunks=[_chunk(fake_summary)])

    result = validate_chunk_snapshot(snapshot, exercise, tmp_path / "runs" / "run")

    assert result.passed is False
    assert result.violations == ["chunk not present in frozen source: abcdef12-3456:0"]


def test_source_chunk_map_resolves_prefixed_short_document_ids(tmp_path: Path) -> None:
    exercise, text = _exercise_with_source(tmp_path)
    chunk = _chunk(text)
    validation = validate_chunk_snapshot(
        ChunkSnapshot(schema_version=1, chunks=[chunk]),
        exercise,
        tmp_path / "runs" / "run",
    )
    sources = [
        {"source_id": "S1", "doc_ids": ["document_id:abcdef12:0"]},
        {"source_id": "S2", "doc_ids": []},
    ]

    mapping = source_chunk_map(sources, validation.valid_chunks)

    assert mapping == {"S1": ["abcdef12-3456:0"], "S2": []}


def test_chunk_snapshot_rejects_payload_hash_mismatch(tmp_path: Path) -> None:
    exercise, text = _exercise_with_source(tmp_path)
    chunk = _chunk(text).model_copy(update={"sha256": "0" * 64})

    result = validate_chunk_snapshot(
        ChunkSnapshot(schema_version=1, chunks=[chunk]),
        exercise,
        tmp_path / "runs" / "run",
    )

    assert result.violations == ["chunk hash mismatch: abcdef12-3456:0"]


def test_resolved_variant_propagates_canonical_filename(tmp_path):
    """Codex review #201 (2026-07-16, bloquant) : le juge filtre les chunks par
    requirement.source_files contre RetrievedChunk.filename. Les fichiers
    runtime sont renommés d'après le titre ; la validation sait les relier au
    corpus gelé via l'URL du frontmatter, mais gardait le nom runtime — les
    items d'adéquation finance recevaient 0 chunk de preuve. Le nom canonique
    du manifeste doit être propagé dans valid_chunks."""
    import hashlib
    import json

    from evaluations.chunk_snapshot import load_chunk_snapshot, validate_chunk_snapshot

    exercise = tmp_path / "exercise"
    corpus = exercise / "corpus"
    corpus.mkdir(parents=True)
    body = "Amazon capex was 40.1B in FY2020.\n"
    (corpus / "capex_reference_data.md").write_text(body, encoding="utf-8")
    (exercise / "source_manifest.yaml").write_text(
        "sources:\n"
        "  - url: https://example.test/raw/capex_reference_data.md\n"
        "    file_pattern: capex_reference_data.md\n"
        f"    sha256: {hashlib.sha256(body.encode()).hexdigest()}\n",
        encoding="utf-8",
    )
    run = tmp_path / "run"
    raw = run / "raw_sources"
    raw.mkdir(parents=True)
    stored = (
        "---\n"
        'title: "Capital Expenditure Reference Data"\n'
        "source: https://example.test/raw/capex_reference_data.md\n"
        "---\n\n"
        "# Capital Expenditure Reference Data\n\n"
        "**Source:** [https://example.test/raw/capex_reference_data.md](https://example.test/raw/capex_reference_data.md)\n\n"
        "## Contenu\n\n" + body
    )
    runtime_name = "Capital-Expenditure_Reference_Data__from_SEC_10-K__1.md"
    (raw / runtime_name).write_text(stored, encoding="utf-8")
    chunk_text = "Amazon capex was 40.1B in FY2020."
    (run / "chunks.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "chunks": [
                    {
                        "chunk_id": "doc-1:0",
                        "document_id": "doc-1",
                        "chunk_index": 0,
                        "filename": runtime_name,
                        "source": "https://example.test/raw/capex_reference_data.md",
                        "text": chunk_text,
                        "sha256": hashlib.sha256(chunk_text.encode()).hexdigest(),
                        "resolved": True,
                    }
                ],
                "conflicts": [],
            }
        ),
        encoding="utf-8",
    )

    result = validate_chunk_snapshot(load_chunk_snapshot(run / "chunks.json"), exercise, run)

    assert result.passed, result.violations
    assert result.valid_chunks["doc-1:0"].filename == "capex_reference_data.md"
