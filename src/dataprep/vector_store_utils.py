"""Shared utilities for vector store ingestion."""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from .knowledge_db import KnowledgeDBManager
from .models import KnowledgeEntry
from .pdf_utils import extract_pdf_text_from_path, is_pdf_path


@dataclass
class ResolvedInput:
    entry: KnowledgeEntry
    file_path: Path
    force_reindex: bool = False


def ensure_local_file_entry(
    input_path: Path, config, db_manager: KnowledgeDBManager
) -> ResolvedInput:
    local_dir = Path(config.data.local_storage_dir)
    local_dir.mkdir(parents=True, exist_ok=True)

    source_path = input_path.resolve()
    filename = input_path.name
    existing_entry = db_manager.find_by_name(filename)
    destination = local_dir / filename
    source_stat = source_path.stat()
    source_changed = _source_has_changed(existing_entry, source_path, source_stat)
    artifacts_missing = _artifacts_missing(existing_entry, local_dir)

    if existing_entry and not source_changed and not artifacts_missing:
        return ResolvedInput(
            entry=existing_entry,
            file_path=resolve_entry_artifact_path(existing_entry, local_dir),
            force_reindex=False,
        )

    if source_path != destination.resolve():
        shutil.copy2(source_path, destination)

    normalized_filename: str | None = None
    content_length = destination.stat().st_size
    if is_pdf_path(source_path):
        normalized_filename = _normalized_artifact_name(filename)
        parsed_pdf = extract_pdf_text_from_path(destination)
        normalized_path = local_dir / normalized_filename
        normalized_path.parent.mkdir(parents=True, exist_ok=True)
        normalized_path.write_text(parsed_pdf.text, encoding="utf-8")
        content_length = parsed_pdf.extracted_chars

    entry = _build_local_entry(
        existing_entry=existing_entry,
        source_path=source_path,
        filename=filename,
        normalized_filename=normalized_filename,
        content_length=content_length,
        source_stat=source_stat,
        source_changed=source_changed,
    )
    db_manager.add_entry(entry)
    return ResolvedInput(
        entry=entry,
        file_path=resolve_entry_artifact_path(entry, local_dir),
        force_reindex=source_changed,
    )


def is_openai_file_id(value: str) -> bool:
    return bool(re.match(r"^file[-_][A-Za-z0-9]+$", value))


def validate_url(url: str) -> None:
    if not url:
        raise ValueError("URL vide")
    if any(ch.isspace() for ch in url):
        raise ValueError(f"URL invalide (espaces): {url}")
    try:
        url.encode("ascii")
    except UnicodeEncodeError as exc:
        raise ValueError(f"URL invalide (non ASCII): {url}") from exc
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError(f"URL invalide (schema): {url}")
    if not parsed.netloc:
        raise ValueError(f"URL invalide (domaine manquant): {url}")


def validate_filename(filename: str) -> None:
    if not filename:
        raise ValueError("Nom de fichier vide")
    if "/" in filename or "\\" in filename:
        raise ValueError(f"Nom de fichier invalide (separateurs): {filename}")
    if filename.startswith(".") or filename in {".", ".."}:
        raise ValueError(f"Nom de fichier invalide: {filename}")
    if ".." in filename:
        raise ValueError(f"Nom de fichier invalide (path traversal): {filename}")
    if len(filename) > 255:
        raise ValueError(f"Nom de fichier trop long: {filename}")
    if not re.match(r"^[A-Za-z0-9._-]+$", filename):
        raise ValueError(f"Nom de fichier invalide (caracteres): {filename}")


def resolve_inputs_to_entries(
    inputs: list[str],
    config,
    db_manager: KnowledgeDBManager,
    local_dir: Path,
) -> list[ResolvedInput]:
    entries_to_process = []

    for input_item in inputs:
        entry = None
        force_reindex = False

        input_path = Path(input_item)

        if is_openai_file_id(input_item):
            entry = db_manager.find_by_openai_file_id(input_item)
            if not entry:
                raise ValueError(f"file_id non trouvé dans la base de connaissances: {input_item}")
        elif input_path.exists():
            if input_path.is_dir():
                raise ValueError(f"Chemin invalide (dossier): {input_item}")
            resolved = ensure_local_file_entry(input_path, config, db_manager)
            entry = resolved.entry
            force_reindex = resolved.force_reindex
        elif input_item.startswith(("http://", "https://")):
            validate_url(input_item)
            entry = db_manager.lookup_url(input_item)
            if not entry:
                raise ValueError(f"URL non trouvée dans la base de connaissances: {input_item}")
        elif "://" in input_item:
            raise ValueError(f"URL invalide (schema): {input_item}")
        else:
            validate_filename(input_item)
            entry = db_manager.find_by_name(input_item)
            if not entry:
                candidate_path = local_dir / input_item
                if candidate_path.exists():
                    resolved = ensure_local_file_entry(candidate_path, config, db_manager)
                    entry = resolved.entry
                    force_reindex = resolved.force_reindex
                else:
                    raise ValueError(
                        f"Fichier non trouvé dans la base de connaissances: {input_item}"
                    )
            elif entry.source_type == "local_file" and entry.source_path:
                resolved = ensure_local_file_entry(Path(entry.source_path), config, db_manager)
                entry = resolved.entry
                force_reindex = resolved.force_reindex

        file_path = resolve_entry_artifact_path(entry, local_dir)
        if not file_path.exists():
            raise FileNotFoundError(f"Fichier local non trouvé: {file_path}")

        entries_to_process.append(
            ResolvedInput(entry=entry, file_path=file_path, force_reindex=force_reindex)
        )

    return entries_to_process


def read_local_file(file_path: Path) -> str:
    with open(file_path, encoding="utf-8") as f:
        return f.read()


def chunk_text(text: str, max_chars: int, overlap: int) -> list[str]:
    chunks = []
    start = 0
    text_length = len(text)
    while start < text_length:
        end = min(start + max_chars, text_length)
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end == text_length:
            break
        start = max(end - overlap, 0)
    return chunks


def resolve_entry_artifact_path(entry: KnowledgeEntry, local_dir: Path) -> Path:
    artifact_filename = entry.normalized_filename or entry.filename
    return local_dir / artifact_filename


def _normalized_artifact_name(filename: str) -> str:
    return str(Path("normalized") / f"{filename}.md")


def _source_has_changed(entry: KnowledgeEntry | None, source_path: Path, source_stat) -> bool:
    if entry is None:
        return False
    if entry.source_type != "local_file":
        return True
    if entry.source_path != str(source_path):
        return True
    if entry.source_last_modified_ns != source_stat.st_mtime_ns:
        return True
    return entry.source_size_bytes != source_stat.st_size


def _artifacts_missing(entry: KnowledgeEntry | None, local_dir: Path) -> bool:
    if entry is None:
        return True
    source_copy = local_dir / entry.filename
    if not source_copy.exists():
        return True
    if entry.normalized_filename and not (local_dir / entry.normalized_filename).exists():
        return True
    return False


def _build_local_entry(
    *,
    existing_entry: KnowledgeEntry | None,
    source_path: Path,
    filename: str,
    normalized_filename: str | None,
    content_length: int,
    source_stat,
    source_changed: bool,
) -> KnowledgeEntry:
    base_entry = existing_entry.model_copy(deep=True) if existing_entry else None
    payload = {
        "url": f"file://{source_path}",
        "filename": filename,
        "source_type": "local_file",
        "source_path": str(source_path),
        "normalized_filename": normalized_filename,
        "source_last_modified_ns": source_stat.st_mtime_ns,
        "source_size_bytes": source_stat.st_size,
        "keywords": base_entry.keywords if base_entry else [],
        "summary": base_entry.summary if base_entry else None,
        "title": base_entry.title if base_entry and base_entry.title else source_path.stem,
        "content_length": content_length,
        "openai_file_id": (
            None if source_changed else (base_entry.openai_file_id if base_entry else None)
        ),
        "vector_doc_id": base_entry.vector_doc_id if base_entry else None,
        "last_uploaded_at": (
            None if source_changed else (base_entry.last_uploaded_at if base_entry else None)
        ),
    }
    if base_entry is not None:
        payload["created_at"] = base_entry.created_at
    return KnowledgeEntry(**payload)
