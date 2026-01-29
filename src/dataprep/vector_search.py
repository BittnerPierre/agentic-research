"""Local vector search backend with late chunking."""

from __future__ import annotations

import json
import logging
import re
import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class VectorSearchHit:
    document: str
    metadata: dict
    score: float


@dataclass
class VectorSearchResult:
    query: str
    results: list[VectorSearchHit]


@dataclass
class VectorSearchDocument:
    content: str
    metadata: dict
    document_id: str


class LocalVectorSearchBackend:
    """File-backed vector search using lexical scoring and late chunking."""

    def __init__(
        self,
        index_path: Path,
        chunk_size: int = 800,
        chunk_overlap: int = 120,
    ) -> None:
        self.index_path = index_path
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.index_path.exists():
            self._write_index([])

    def add_documents(self, documents: Iterable[VectorSearchDocument]) -> list[str]:
        index = self._read_index()
        new_ids: list[str] = []

        for doc in documents:
            index.append(
                {
                    "document_id": doc.document_id,
                    "content": doc.content,
                    "metadata": doc.metadata,
                }
            )
            new_ids.append(doc.document_id)

        self._write_index(index)
        return new_ids

    def has_document(self, document_id: str) -> bool:
        index = self._read_index()
        return any(record.get("document_id") == document_id for record in index)

    def query(self, query: str, top_k: int, score_threshold: float | None) -> list[VectorSearchHit]:
        query_tokens = _tokenize(query)
        if not query_tokens:
            return []

        index = self._read_index()
        hits: list[VectorSearchHit] = []
        query_token_set = set(query_tokens)

        for record in index:
            content = record.get("content", "")
            metadata = record.get("metadata", {})
            for chunk_index, chunk in enumerate(
                _chunk_text(content, self.chunk_size, self.chunk_overlap)
            ):
                score = _score_chunk(query_token_set, chunk)
                if score_threshold is not None and score < score_threshold:
                    continue
                hit_metadata = {
                    **metadata,
                    "chunk_index": chunk_index,
                    "document_id": record.get("document_id"),
                }
                hits.append(VectorSearchHit(document=chunk, metadata=hit_metadata, score=score))

        hits.sort(key=lambda item: item.score, reverse=True)
        return hits[:top_k]

    def _read_index(self) -> list[dict]:
        try:
            with open(self.index_path, encoding="utf-8") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return []

    def _write_index(self, records: list[dict]) -> None:
        with open(self.index_path, "w", encoding="utf-8") as f:
            json.dump(records, f, ensure_ascii=True, indent=2)


def get_vector_search_backend(config) -> LocalVectorSearchBackend:
    base_dir = Path(config.data.local_storage_dir) / "vector_index"
    index_name = config.vector_search.index_name
    index_path = base_dir / f"{index_name}.json"
    return LocalVectorSearchBackend(index_path=index_path)


def create_document(
    content: str, metadata: dict, document_id: str | None = None
) -> VectorSearchDocument:
    return VectorSearchDocument(
        content=content,
        metadata=metadata,
        document_id=document_id or str(uuid.uuid4()),
    )


def _chunk_text(text: str, max_chars: int, overlap: int) -> Iterable[str]:
    start = 0
    text_length = len(text)

    while start < text_length:
        end = min(start + max_chars, text_length)
        chunk = text[start:end].strip()
        if chunk:
            yield chunk
        if end == text_length:
            break
        start = max(end - overlap, 0)


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def _score_chunk(query_tokens: set[str], chunk: str) -> float:
    chunk_tokens = set(_tokenize(chunk))
    if not chunk_tokens:
        return 0.0
    overlap = query_tokens.intersection(chunk_tokens)
    return len(overlap) / max(len(query_tokens), 1)
