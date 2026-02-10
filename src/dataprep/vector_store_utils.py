"""Shared utilities for vector store ingestion."""

from __future__ import annotations

import re
import shutil
from pathlib import Path
from urllib.parse import urlparse

from .knowledge_db import KnowledgeDBManager
from .models import KnowledgeEntry


def ensure_local_file_entry(
    input_path: Path, config, db_manager: KnowledgeDBManager
) -> KnowledgeEntry:
    local_dir = Path(config.data.local_storage_dir)
    local_dir.mkdir(parents=True, exist_ok=True)

    filename = input_path.name
    existing_entry = db_manager.find_by_name(filename)
    if existing_entry:
        return existing_entry

    destination = local_dir / filename
    if input_path.resolve() != destination.resolve():
        shutil.copy2(input_path, destination)

    title = input_path.stem
    content_length = destination.stat().st_size

    entry = KnowledgeEntry(
        url=f"file://{input_path.resolve()}",
        filename=filename,
        keywords=[],
        summary=None,
        title=title,
        content_length=content_length,
    )
    db_manager.add_entry(entry)
    return entry


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
) -> list[tuple[KnowledgeEntry, Path]]:
    entries_to_process = []

    for input_item in inputs:
        entry = None

        input_path = Path(input_item)

        if is_openai_file_id(input_item):
            entry = db_manager.find_by_openai_file_id(input_item)
            if not entry:
                raise ValueError(f"file_id non trouvé dans la base de connaissances: {input_item}")
        elif input_path.exists():
            if input_path.is_dir():
                raise ValueError(f"Chemin invalide (dossier): {input_item}")
            entry = ensure_local_file_entry(input_path, config, db_manager)
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
                    entry = ensure_local_file_entry(candidate_path, config, db_manager)
                else:
                    raise ValueError(
                        f"Fichier non trouvé dans la base de connaissances: {input_item}"
                    )

        file_path = local_dir / entry.filename
        if not file_path.exists():
            raise FileNotFoundError(f"Fichier local non trouvé: {file_path}")

        entries_to_process.append((entry, file_path))

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
