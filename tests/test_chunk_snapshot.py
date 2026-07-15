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
