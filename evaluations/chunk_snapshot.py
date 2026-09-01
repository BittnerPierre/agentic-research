"""Portable, deterministic validation of raw retrieval evidence."""

from __future__ import annotations

import fnmatch
import hashlib
import json
import re
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.dataprep.vector_backends import clean_for_rag


class RetrievedChunk(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chunk_id: str | None = None
    document_id: str | None = None
    chunk_index: int | str | None = None
    filename: str | None = None
    source: str | None = None
    text: str
    sha256: str
    resolved: bool


class ChunkConflict(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chunk_id: str | None = None
    first_sha256: str
    second_sha256: str


class ChunkSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: int = Field(ge=1)
    chunks: list[RetrievedChunk]
    conflicts: list[ChunkConflict] = Field(default_factory=list)

    @model_validator(mode="after")
    def unique_resolved_chunk_ids(self) -> ChunkSnapshot:
        resolved_ids = [chunk.chunk_id for chunk in self.chunks if chunk.resolved]
        if len(resolved_ids) != len(set(resolved_ids)):
            raise ValueError("resolved chunk ids must be unique")
        return self


class ChunkValidationResult(BaseModel):
    valid_chunks: dict[str, RetrievedChunk] = Field(default_factory=dict)
    unresolved_chunks: list[str] = Field(default_factory=list)
    nonportable_chunks: list[str] = Field(default_factory=list)
    violations: list[str] = Field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not self.violations


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def load_chunk_snapshot(path: Path) -> ChunkSnapshot:
    return ChunkSnapshot.model_validate_json(path.read_text(encoding="utf-8"))


def _source_roots(exercise: Path, run_dir: Path) -> list[Path]:
    roots = [run_dir / "raw_sources", exercise / "corpus"]
    if len(run_dir.parents) >= 3:
        roots.append(run_dir.parents[2] / "data")
    return roots


def _manifest_source(filename: str, manifest: dict) -> dict | None:
    matches = [
        source
        for source in manifest.get("sources") or []
        if fnmatch.fnmatch(filename, source["file_pattern"])
    ]
    return matches[0] if len(matches) == 1 else None


_FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---\n", re.S)


def _frontmatter_and_body(text: str) -> tuple[dict, str]:
    """Split the ingestion frontmatter (title/source/…) from the stored body."""
    match = _FRONTMATTER_RE.match(text)
    if not match:
        return {}, text
    meta: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            meta[key.strip()] = value.strip().strip('"')
    return meta, text[match.end() :]


def _resolve_stored_variant(
    filename: str,
    manifest: dict,
    roots: list[Path],
) -> tuple[dict | None, Path | None, str | None]:
    """Match a title-renamed ingested file back to its frozen manifest entry.

    The ingestion pipeline renames downloads after the document title and adds a
    frontmatter block recording the exact ``source`` URL. The frozen manifest
    keys on the canonical corpus filenames (the URL basenames). Resolution is
    only accepted when the frontmatter-stripped BODY hash equals the frozen
    corpus hash — the security property (chunks provably come from the frozen
    content) is preserved; only the filename indirection is bridged.
    """
    for root in roots:
        path = root / filename
        if not path.is_file():
            continue
        meta, body = _frontmatter_and_body(path.read_text(encoding="utf-8", errors="ignore"))
        url = meta.get("source", "")
        if not url:
            continue
        canonical = url.split("?", 1)[0].rstrip("/").rsplit("/", 1)[-1]
        expected = _manifest_source(canonical, manifest)
        if expected is None:
            continue
        frozen_file = _frozen_source_file(canonical, expected, roots)
        if frozen_file is None:
            continue
        if (
            _strip_ingestion_preamble(body)
            != frozen_file.read_text(encoding="utf-8", errors="ignore").strip()
        ):
            continue
        return expected, path, canonical
    return None, None, None


def _strip_ingestion_preamble(body: str) -> str:
    """Drop the loader-added preamble (# title / **Source:** url / ## Contenu).

    The storage pipeline prepends exactly these lines before the verbatim
    downloaded content. Anything beyond this known pattern is NOT stripped, so
    a stored file with extra injected content will fail the equality check."""
    lines = body.lstrip("\n").splitlines()
    index = 0
    if index < len(lines) and lines[index].startswith("# "):
        index += 1
        while index < len(lines) and not lines[index].strip():
            index += 1
    if index < len(lines) and lines[index].startswith("**Source:**"):
        index += 1
        while index < len(lines) and not lines[index].strip():
            index += 1
    if index < len(lines) and lines[index].strip().lower() in {"## contenu", "## content"}:
        index += 1
        while index < len(lines) and not lines[index].strip():
            index += 1
    end = len(lines)
    while end > index and not lines[end - 1].strip():
        end -= 1
    # Known trailing footer:
    # "---" + "*Document traité automatiquement par le système de recherche agentique*"
    if end > index and re.fullmatch(
        r"\*Document[^*\n]*(?:automatiquement|agentique|automatically|retrieved)[^*\n]*\*",
        lines[end - 1].strip(),
    ):
        end -= 1
        while end > index and lines[end - 1].strip() in {"---", ""}:
            end -= 1
    return "\n".join(lines[index:end]).strip()


def load_source_manifest(exercise: Path) -> tuple[Path | None, dict]:
    """Load either supported frozen-corpus manifest into one internal schema."""
    yaml_path = exercise / "source_manifest.yaml"
    if yaml_path.is_file():
        return yaml_path, yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}

    json_path = exercise / "corpus" / "manifest.json"
    if not json_path.is_file():
        return None, {}
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    generated_files = payload.get("generated_files") or {}
    return json_path, {
        "sources": [
            {"file_pattern": filename, "sha256": sha256}
            for filename, sha256 in sorted(generated_files.items())
        ]
    }


def _frozen_source_file(
    filename: str,
    expected: dict,
    roots: list[Path],
) -> Path | None:
    candidates = [
        path
        for root in roots
        for path in root.glob(expected["file_pattern"])
        if path.is_file() and path.name == filename
    ]
    return next(
        (path for path in candidates if _sha256_bytes(path.read_bytes()) == expected["sha256"]),
        None,
    )


def validate_chunk_snapshot(
    snapshot: ChunkSnapshot,
    exercise: Path,
    run_dir: Path,
) -> ChunkValidationResult:
    manifest_path, manifest = load_source_manifest(exercise)
    if manifest_path is None:
        return ChunkValidationResult(violations=["source manifest unavailable"])
    roots = _source_roots(exercise, run_dir)
    result = ChunkValidationResult()

    if snapshot.conflicts:
        result.violations.append("conflicting payloads for stable chunk ids")

    source_texts: dict[Path, tuple[str, str]] = {}
    for chunk in snapshot.chunks:
        label = chunk.chunk_id or f"unresolved:{chunk.sha256[:12]}"
        if _sha256_bytes(chunk.text.encode("utf-8")) != chunk.sha256:
            result.violations.append(f"chunk hash mismatch: {label}")
            continue
        if not chunk.resolved or not chunk.chunk_id:
            result.unresolved_chunks.append(label)
            continue
        if not chunk.filename:
            result.violations.append(f"resolved chunk missing filename: {label}")
            continue
        expected = _manifest_source(chunk.filename, manifest)
        source_file: Path | None = None
        if expected is None:
            # Title-renamed ingested copy: bridge via its frontmatter source URL,
            # accepted only when the stripped body hash-matches the frozen corpus.
            expected, source_file, canonical = _resolve_stored_variant(
                chunk.filename, manifest, roots
            )
            if canonical:
                # Propagate the CANONICAL manifest name: downstream consumers
                # (semantic judge source_files filter) match on it — the runtime
                # title-renamed name gave finance adequacy items zero evidence
                # (Codex review 2026-07-16).
                chunk = chunk.model_copy(update={"filename": canonical})
        if expected is None:
            result.violations.append(f"chunk source outside frozen manifest: {label}")
            continue
        if source_file is None:
            source_file = _frozen_source_file(chunk.filename, expected, roots)
        if source_file is None:
            result.violations.append(f"frozen source unavailable or hash mismatch: {label}")
            continue
        if source_file not in source_texts:
            raw_text = source_file.read_text(encoding="utf-8", errors="ignore")
            source_texts[source_file] = (raw_text, clean_for_rag(raw_text))
        raw_text, cleaned_text = source_texts[source_file]
        if chunk.text not in raw_text and chunk.text not in cleaned_text:
            result.violations.append(f"chunk not present in frozen source: {label}")
            continue
        result.valid_chunks[chunk.chunk_id] = chunk
        if not source_file.is_relative_to(run_dir / "raw_sources"):
            result.nonportable_chunks.append(label)

    result.unresolved_chunks.sort()
    result.nonportable_chunks.sort()
    result.violations = sorted(set(result.violations))
    return result


def resolve_chunk_id(raw_id: str, valid_chunks: dict[str, RetrievedChunk]) -> str | None:
    candidate = str(raw_id).removeprefix("document_id:")
    if candidate in valid_chunks:
        return candidate
    if ":" not in candidate:
        return None
    document_prefix, chunk_index = candidate.rsplit(":", 1)
    matches = [
        chunk_id
        for chunk_id in valid_chunks
        if chunk_id.rsplit(":", 1)[1] == chunk_index
        and chunk_id.rsplit(":", 1)[0].startswith(document_prefix)
    ]
    if len(matches) == 1:
        return matches[0]
    # Notation « filename:index » (arbitrage Pierre 2026-07-17, DeepSeek) :
    # l'agent transcode l'UUID en identifiant lisible. La référence est
    # complète et non ambiguë — le pack porte filename et chunk_index — donc
    # le code résout déterministiquement. Refusé si plusieurs candidats.
    by_file = [
        chunk_id
        for chunk_id, chunk in valid_chunks.items()
        if chunk.filename == document_prefix and str(chunk.chunk_index) == chunk_index
    ]
    return by_file[0] if len(by_file) == 1 else None


def source_chunk_map(
    sources: list[dict],
    valid_chunks: dict[str, RetrievedChunk],
) -> dict[str, list[str]]:
    mapping: dict[str, list[str]] = {}
    for source in sources:
        source_id = str(source.get("source_id") or "").upper()
        if not source_id:
            continue
        resolved = [
            chunk_id
            for raw_id in source.get("doc_ids") or []
            if (chunk_id := resolve_chunk_id(str(raw_id), valid_chunks)) is not None
        ]
        mapping[source_id] = list(dict.fromkeys(resolved))
    return mapping


def write_chunk_snapshot(path: Path, payload: dict) -> None:
    snapshot = ChunkSnapshot.model_validate(payload)
    path.write_text(
        json.dumps(snapshot.model_dump(mode="json"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
