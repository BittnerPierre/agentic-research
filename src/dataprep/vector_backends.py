"""Vector store backend implementations."""

from __future__ import annotations

import logging
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, ClassVar, Protocol

import chromadb
from openai import OpenAI

from .chroma_embedding_factory import get_chroma_embedding_function
from .knowledge_db import KnowledgeDBManager
from .models import UploadResult
from .vector_search import (
    VectorSearchHit,
    VectorSearchResult,
    create_document,
    get_vector_search_backend,
)
from .vector_store_manager import VectorStoreManager
from .vector_store_utils import chunk_text, read_local_file, resolve_inputs_to_entries

logger = logging.getLogger(__name__)

MIN_CHARS_PER_CHUNK = 200

_NOISE_SECTION_MARKERS = (
    "## references",
    "## see also",
    "retrieved from",
    "categories:",
    "hidden categories:",
)
_NOISE_LINE_RE = re.compile(
    r"(\[\[edit\]|cookie|open in app|sitemap|copy as markdown|ask docs ai|page not found)",
    re.IGNORECASE,
)
_ARTIFACT_RE = re.compile(
    r"(RECOMMENDED_PROMPT_PREFIX|You are a|system prompt|tool_call|BEGIN|END)",
    re.IGNORECASE,
)


def _strip_front_matter(text: str) -> str:
    return re.sub(r"\A---\n.*?\n---\n", "", text, flags=re.DOTALL)


def _strip_markdown_links(text: str) -> str:
    return re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)


def _clean_for_rag(text: str) -> str:
    cleaned = _strip_front_matter(text)
    cleaned = re.sub(r"```[\s\S]*?```", "\n", cleaned)
    cleaned = cleaned.replace(
        "*Document traité automatiquement par le système de recherche agentique*", ""
    )
    cleaned = re.sub(r"</[^>]+>", "", cleaned)
    cleaned = re.sub(r"\[\[edit\][^\]]*\]", "", cleaned, flags=re.IGNORECASE)
    cleaned = cleaned.replace("\\(", "(").replace("\\)", ")")
    cleaned = _strip_markdown_links(cleaned)

    kept_lines: list[str] = []
    for raw_line in cleaned.splitlines():
        line = raw_line.strip()
        lowered = line.lower()
        if any(marker in lowered for marker in _NOISE_SECTION_MARKERS):
            break
        if _NOISE_LINE_RE.search(line):
            continue
        kept_lines.append(line)

    cleaned = "\n".join(kept_lines)
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def _chunk_dense_text(text: str, max_chars: int, overlap: int) -> list[str]:
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]
    if not paragraphs:
        return []

    chunks: list[str] = []
    current = ""

    def _flush(value: str) -> None:
        if value:
            chunks.append(value.strip())

    for paragraph in paragraphs:
        if len(paragraph) > max_chars:
            _flush(current)
            current = ""
            for part in chunk_text(paragraph, max_chars=max_chars, overlap=overlap):
                _flush(part)
            continue

        if not current:
            current = paragraph
            continue

        candidate = f"{current}\n\n{paragraph}"
        if len(candidate) <= max_chars:
            current = candidate
            continue

        _flush(current)
        if overlap > 0 and len(current) > overlap:
            current = f"{current[-overlap:]}\n\n{paragraph}"
            if len(current) > max_chars:
                current = paragraph
        else:
            current = paragraph

    _flush(current)
    return chunks


def _non_alnum_ratio(text: str) -> float:
    if not text:
        return 1.0
    non_alnum = sum(1 for c in text if (not c.isalnum() and not c.isspace()))
    return non_alnum / len(text)


def _is_high_quality_chunk(chunk: str) -> bool:
    if len(chunk) < 200:
        return False
    if _non_alnum_ratio(chunk) > 0.45:
        return False
    if _ARTIFACT_RE.search(chunk):
        return False
    if chunk.count("http") > 6:
        return False
    return True


def _normalize_filenames(filenames: list[str] | None) -> list[str]:
    if not filenames:
        return []
    normalized: list[str] = []
    for name in filenames:
        cleaned = str(name).strip()
        if cleaned:
            normalized.append(cleaned)
    return normalized


def _openai_search_results_to_hits(
    response, score_threshold: float | None
) -> list[VectorSearchHit]:
    data = getattr(response, "data", None)
    if data is None and isinstance(response, dict):
        data = response.get("data")
    if not data:
        return []

    hits: list[VectorSearchHit] = []
    for item in data:
        item_dict = item
        if not isinstance(item_dict, dict):
            if hasattr(item, "model_dump"):
                item_dict = item.model_dump()
            elif hasattr(item, "__dict__"):
                item_dict = item.__dict__
            else:
                item_dict = {"content": None}

        score = item_dict.get("score")
        if score_threshold is not None and score is not None and score < score_threshold:
            continue

        content_blocks = item_dict.get("content") or []
        text_parts: list[str] = []
        for block in content_blocks:
            block_dict = block
            if not isinstance(block_dict, dict):
                if hasattr(block, "model_dump"):
                    block_dict = block.model_dump()
                elif hasattr(block, "__dict__"):
                    block_dict = block.__dict__
                else:
                    block_dict = {}
            if block_dict.get("type") == "text" and block_dict.get("text"):
                text_parts.append(str(block_dict.get("text")))
        document = "\n".join(text_parts).strip()

        metadata: dict[str, Any] = {}
        filename = item_dict.get("filename")
        if filename:
            metadata["filename"] = filename
        file_id = item_dict.get("file_id")
        if file_id:
            metadata["document_id"] = file_id
        attributes = item_dict.get("attributes")
        if attributes:
            metadata["attributes"] = attributes

        hits.append(
            VectorSearchHit(
                document=document,
                metadata=metadata,
                score=score if score is not None else 0.0,
            )
        )

    return hits


class VectorBackend(Protocol):
    provider: str

    def resolve_store_id(self, vectorstore_name: str, config) -> str | None:
        """Resolve a provider-specific store identifier."""

    def upload_files(self, inputs: list[str], config, vectorstore_name: str) -> UploadResult:
        """Upload or index files into the backend."""

    def search(
        self,
        query: str,
        config,
        top_k: int | None = None,
        score_threshold: float | None = None,
        filenames: list[str] | None = None,
        vectorstore_id: str | None = None,
    ) -> VectorSearchResult:
        """Search over locally indexed documents."""

    def tool_name(self) -> str:
        """Return the tool name used in trajectories."""


class VectorStoreRegistry:
    _store_ids: ClassVar[dict[tuple[str, str], str]] = {}

    @classmethod
    def get(cls, provider: str, name: str) -> str | None:
        return cls._store_ids.get((provider, name))

    @classmethod
    def set(cls, provider: str, name: str, store_id: str) -> None:
        cls._store_ids[(provider, name)] = store_id


class LocalVectorBackend:
    provider = "local"

    def resolve_store_id(self, vectorstore_name: str, config) -> str | None:
        config.vector_search.index_name = vectorstore_name
        VectorStoreRegistry.set(self.provider, vectorstore_name, vectorstore_name)
        return None

    def upload_files(self, inputs: list[str], config, vectorstore_name: str) -> UploadResult:
        start_time = time.perf_counter()
        logger.info(f"[upload_files_to_vectorstore] Starting with {len(inputs)} inputs")

        db_manager = KnowledgeDBManager(config.data.knowledge_db_path)
        local_dir = Path(config.data.local_storage_dir)
        vectorstore_id = vectorstore_name
        config.vector_search.index_name = vectorstore_name
        backend = get_vector_search_backend(config)

        logger.debug("[upload_files_to_vectorstore] Step 1: Resolving inputs to knowledge entries")
        entries_to_process = resolve_inputs_to_entries(inputs, config, db_manager, local_dir)

        step1_time = time.perf_counter()
        logger.info(
            "[upload_files_to_vectorstore] Step 1 completed in "
            f"{step1_time - start_time:.2f}s - {len(entries_to_process)} entries"
        )

        step2_time = time.perf_counter()
        logger.info(
            "[upload_files_to_vectorstore] Step 2 completed in "
            f"{step2_time - step1_time:.2f}s - Vector store: {vectorstore_id}"
        )

        logger.debug("[upload_files_to_vectorstore] Step 3: Indexing documents locally")
        files_uploaded: list[dict] = []
        files_attached: list[dict] = []
        upload_count = 0
        reuse_count = 0

        documents_to_index = []
        entries_indexed = []

        for entry, file_path in entries_to_process:
            if entry.vector_doc_id and backend.has_document(entry.vector_doc_id):
                files_uploaded.append(
                    {"filename": entry.filename, "doc_id": entry.vector_doc_id, "status": "reused"}
                )
                reuse_count += 1
                continue

            doc_id = entry.vector_doc_id or None
            content = read_local_file(file_path)
            metadata = {"filename": entry.filename, "source": entry.url}
            document = create_document(content=content, metadata=metadata, document_id=doc_id)
            documents_to_index.append(document)
            entries_indexed.append((entry, document.document_id))

        indexed_ids = backend.add_documents(documents_to_index) if documents_to_index else []
        for (entry, doc_id), _ in zip(entries_indexed, indexed_ids, strict=False):
            db_manager.update_vector_doc_id(entry.filename, doc_id)
            files_uploaded.append(
                {"filename": entry.filename, "doc_id": doc_id, "status": "indexed"}
            )
            upload_count += 1

        step3_time = time.perf_counter()
        logger.info(
            "[upload_files_to_vectorstore] Step 3 completed in "
            f"{step3_time - step2_time:.2f}s - Indexed: {upload_count}, Reused: {reuse_count}"
        )

        total_time = time.perf_counter() - start_time
        logger.info(f"[upload_files_to_vectorstore] TOTAL TIME: {total_time:.2f}s")

        return UploadResult(
            vectorstore_id=vectorstore_id,
            files_uploaded=files_uploaded,
            files_attached=files_attached,
            total_files_requested=len(inputs),
            upload_count=upload_count,
            reuse_count=reuse_count,
            attach_success_count=0,
            attach_failure_count=0,
        )

    def search(
        self,
        query: str,
        config,
        top_k: int | None = None,
        score_threshold: float | None = None,
        filenames: list[str] | None = None,
        vectorstore_id: str | None = None,
    ) -> VectorSearchResult:
        from . import vector_search as vector_search_module

        backend = vector_search_module.get_vector_search_backend(config)
        effective_top_k = top_k if top_k is not None else config.vector_search.top_k
        effective_top_k = min(effective_top_k, 50)
        effective_threshold = (
            score_threshold if score_threshold is not None else config.vector_search.score_threshold
        )
        hits = backend.query(
            query=query,
            top_k=effective_top_k,
            score_threshold=effective_threshold,
            filenames=filenames,
        )
        return VectorSearchResult(query=query, results=hits[:effective_top_k])

    def tool_name(self) -> str:
        return "vector_search"


class OpenAIVectorBackend:
    provider = "openai"

    def resolve_store_id(self, vectorstore_name: str, config) -> str | None:
        cached = VectorStoreRegistry.get(self.provider, vectorstore_name)
        if cached:
            return cached
        vector_store_manager = VectorStoreManager(vectorstore_name)
        vector_store_id = vector_store_manager.get_or_create_vector_store()
        VectorStoreRegistry.set(self.provider, vectorstore_name, vector_store_id)
        return vector_store_id

    def upload_files(self, inputs: list[str], config, vectorstore_name: str) -> UploadResult:
        start_time = time.perf_counter()
        logger.info(f"[upload_files_to_vectorstore] Starting with {len(inputs)} inputs")

        db_manager = KnowledgeDBManager(config.data.knowledge_db_path)
        local_dir = Path(config.data.local_storage_dir)
        client = OpenAI()

        logger.debug("[upload_files_to_vectorstore] Step 1: Resolving inputs to knowledge entries")
        entries_to_process = resolve_inputs_to_entries(inputs, config, db_manager, local_dir)

        step1_time = time.perf_counter()
        logger.info(
            "[upload_files_to_vectorstore] Step 1 completed in "
            f"{step1_time - start_time:.2f}s - {len(entries_to_process)} entries"
        )

        logger.debug("[upload_files_to_vectorstore] Step 2: Creating/getting vector store")
        vector_store_id = self.resolve_store_id(vectorstore_name, config)

        step2_time = time.perf_counter()
        logger.info(
            "[upload_files_to_vectorstore] Step 2 completed in "
            f"{step2_time - step1_time:.2f}s - Vector store: {vector_store_id}"
        )

        logger.debug("[upload_files_to_vectorstore] Step 3: Processing files (upload if needed)")
        files_uploaded: list[dict] = []
        files_to_attach: list[tuple[str, str]] = []
        upload_count = 0
        reuse_count = 0

        for entry, file_path in entries_to_process:
            if entry.openai_file_id:
                logger.info(
                    f"Reusing existing OpenAI file: {entry.filename} -> {entry.openai_file_id}"
                )
                files_uploaded.append(
                    {
                        "filename": entry.filename,
                        "file_id": entry.openai_file_id,
                        "status": "reused",
                    }
                )
                files_to_attach.append((entry.openai_file_id, entry.filename))
                reuse_count += 1
            else:
                try:
                    logger.info(f"Uploading new file: {entry.filename}")
                    with open(file_path, "rb") as file:
                        file_upload_response = client.files.create(file=file, purpose="user_data")

                    file_id = file_upload_response.id

                    db_manager.update_openai_file_id(entry.filename, file_id)

                    files_uploaded.append(
                        {"filename": entry.filename, "file_id": file_id, "status": "uploaded"}
                    )
                    files_to_attach.append((file_id, entry.filename))
                    upload_count += 1
                except Exception as e:
                    logger.error(f"Upload error {entry.filename}: {e}")
                    files_uploaded.append(
                        {"filename": entry.filename, "error": str(e), "status": "failed"}
                    )

        step3_time = time.perf_counter()
        logger.info(
            "[upload_files_to_vectorstore] Step 3 completed in "
            f"{step3_time - step2_time:.2f}s - Uploaded: {upload_count}, Reused: {reuse_count}"
        )

        logger.debug(
            "[upload_files_to_vectorstore] Step 4: Attaching files to vector store (parallel)"
        )

        def attach_single_file(file_id: str, filename: str) -> dict:
            try:
                vector_store_file = client.vector_stores.files.create(
                    vector_store_id=vector_store_id,
                    file_id=file_id,
                )
                logger.info(
                    f"File attached to vector store: {filename} (status: {vector_store_file.status})"
                )
                return {
                    "filename": filename,
                    "file_id": file_id,
                    "vector_store_file_id": vector_store_file.id,
                    "status": vector_store_file.status,
                    "success": True,
                }
            except Exception as e:
                logger.error(f"Attachment error {filename}: {e}")
                return {
                    "filename": filename,
                    "file_id": file_id,
                    "error": str(e),
                    "status": "attach_failed",
                    "success": False,
                }

        files_attached: list[dict] = []
        attach_success_count = 0
        attach_failure_count = 0

        if not files_to_attach:
            logger.info("[upload_files_to_vectorstore] Step 4 skipped - No files to attach")
        else:
            with ThreadPoolExecutor(max_workers=min(len(files_to_attach), 10)) as executor:
                future_to_file = {
                    executor.submit(attach_single_file, file_id, filename): (file_id, filename)
                    for file_id, filename in files_to_attach
                }
                for future in as_completed(future_to_file):
                    result = future.result()
                    files_attached.append(result)
                    if result.get("success", False):
                        attach_success_count += 1
                    else:
                        attach_failure_count += 1

        step4_time = time.perf_counter()
        logger.info(
            "[upload_files_to_vectorstore] Step 4 completed in "
            f"{step4_time - step3_time:.2f}s (parallel) - "
            f"Attached: {attach_success_count}, Failed: {attach_failure_count}"
        )

        total_time = time.perf_counter() - start_time
        logger.info(f"[upload_files_to_vectorstore] TOTAL TIME: {total_time:.2f}s")

        return UploadResult(
            vectorstore_id=vector_store_id or "",
            files_uploaded=files_uploaded,
            files_attached=files_attached,
            total_files_requested=len(inputs),
            upload_count=upload_count,
            reuse_count=reuse_count,
            attach_success_count=attach_success_count,
            attach_failure_count=attach_failure_count,
        )

    def search(
        self,
        query: str,
        config,
        top_k: int | None = None,
        score_threshold: float | None = None,
        filenames: list[str] | None = None,
        vectorstore_id: str | None = None,
    ) -> VectorSearchResult:
        effective_top_k = top_k if top_k is not None else config.vector_search.top_k
        effective_threshold = (
            score_threshold if score_threshold is not None else config.vector_search.score_threshold
        )
        resolved_store_id = (
            vectorstore_id
            or config.vector_store.vector_store_id
            or self.resolve_store_id(config.vector_store.name, config)
        )
        if not resolved_store_id:
            raise ValueError("OpenAI vector store id is required for vector_search")

        client = OpenAI()
        search_kwargs = {
            "vector_store_id": resolved_store_id,
            "query": query,
            "max_num_results": effective_top_k,
        }
        response = client.vector_stores.search(**search_kwargs)
        hits = _openai_search_results_to_hits(response, effective_threshold)
        return VectorSearchResult(query=query, results=hits[:effective_top_k])

    def tool_name(self) -> str:
        return "vector_search"


def get_vector_backend(config) -> VectorBackend:
    provider = config.vector_search.provider
    if provider == "local":
        return LocalVectorBackend()
    if provider == "openai":
        return OpenAIVectorBackend()
    if provider == "chroma":
        return ChromaVectorBackend()
    raise ValueError(f"Unknown vector_search.provider: {provider}")


class ChromaVectorBackend:
    provider = "chroma"

    def _client(self, config) -> chromadb.HttpClient:
        return chromadb.HttpClient(
            host=config.vector_search.chroma_host,
            port=config.vector_search.chroma_port,
            ssl=config.vector_search.chroma_ssl,
        )

    def _collection(self, config, name: str):
        client = self._client(config)
        embedding_function = get_chroma_embedding_function(config)
        return client.get_or_create_collection(name=name, embedding_function=embedding_function)

    def _collection_has_document(self, collection, doc_id: str) -> bool:
        try:
            result = collection.get(where={"document_id": doc_id}, limit=1)
        except Exception:
            logger.warning(
                "[upload_files_to_vectorstore] Failed to check collection for document_id=%s",
                doc_id,
            )
            return False
        ids = result.get("ids") if isinstance(result, dict) else None
        return bool(ids)

    def _collection_has_any_filename(self, collection, filenames: list[str]) -> bool:
        if not filenames:
            return False
        if len(filenames) == 1:
            where = {"filename": filenames[0]}
        else:
            where = {"filename": {"$in": filenames}}
        try:
            result = collection.get(where=where, limit=1)
        except Exception:
            logger.warning(
                "[vector_search] Failed to check collection for filenames=%s",
                filenames,
            )
            return False
        ids = result.get("ids") if isinstance(result, dict) else None
        return bool(ids)

    def resolve_store_id(self, vectorstore_name: str, config) -> str | None:
        config.vector_search.index_name = vectorstore_name
        VectorStoreRegistry.set(self.provider, vectorstore_name, vectorstore_name)
        return vectorstore_name

    def upload_files(self, inputs: list[str], config, vectorstore_name: str) -> UploadResult:
        start_time = time.perf_counter()
        logger.info(f"[upload_files_to_vectorstore] Starting with {len(inputs)} inputs")

        db_manager = KnowledgeDBManager(config.data.knowledge_db_path)
        local_dir = Path(config.data.local_storage_dir)
        collection = self._collection(config, vectorstore_name)

        logger.debug("[upload_files_to_vectorstore] Step 1: Resolving inputs to knowledge entries")
        entries_to_process = resolve_inputs_to_entries(inputs, config, db_manager, local_dir)

        step1_time = time.perf_counter()
        logger.info(
            "[upload_files_to_vectorstore] Step 1 completed in "
            f"{step1_time - start_time:.2f}s - {len(entries_to_process)} entries"
        )

        files_uploaded: list[dict] = []
        files_attached: list[dict] = []
        upload_count = 0
        reuse_count = 0

        for entry, file_path in entries_to_process:
            if entry.vector_doc_id and self._collection_has_document(
                collection, entry.vector_doc_id
            ):
                files_uploaded.append(
                    {"filename": entry.filename, "doc_id": entry.vector_doc_id, "status": "reused"}
                )
                reuse_count += 1
                continue

            content = read_local_file(file_path)
            cleaned_content = _clean_for_rag(content)
            raw_chunks = _chunk_dense_text(
                cleaned_content,
                max_chars=config.vector_search.chunk_size,
                overlap=config.vector_search.chunk_overlap,
            )
            if len(cleaned_content) < MIN_CHARS_PER_CHUNK:
                # Keep short documents indexable (smoke/fixtures), otherwise they
                # disappear entirely from the collection.
                chunks = raw_chunks
            else:
                chunks = [chunk for chunk in raw_chunks if _is_high_quality_chunk(chunk)]
            if chunks:
                deduped_chunks = list(dict.fromkeys(chunks))
                chunks = deduped_chunks
            if not chunks:
                logger.warning(
                    "[upload_files_to_vectorstore] Skipping %s after cleaning/quality filtering",
                    entry.filename,
                )
                continue

            doc_id = entry.vector_doc_id or f"doc_{entry.filename}"
            ids = [f"{doc_id}:{idx}" for idx in range(len(chunks))]
            metadatas = [
                {
                    "filename": entry.filename,
                    "source": entry.url,
                    "chunk_index": idx,
                    "document_id": doc_id,
                }
                for idx in range(len(chunks))
            ]

            collection.add(
                ids=ids,
                documents=chunks,
                metadatas=metadatas,
            )

            db_manager.update_vector_doc_id(entry.filename, doc_id)
            files_uploaded.append(
                {"filename": entry.filename, "doc_id": doc_id, "status": "indexed"}
            )
            upload_count += 1

        total_time = time.perf_counter() - start_time
        logger.info(f"[upload_files_to_vectorstore] TOTAL TIME: {total_time:.2f}s")

        return UploadResult(
            vectorstore_id=vectorstore_name,
            files_uploaded=files_uploaded,
            files_attached=files_attached,
            total_files_requested=len(inputs),
            upload_count=upload_count,
            reuse_count=reuse_count,
            attach_success_count=0,
            attach_failure_count=0,
        )

    def search(
        self,
        query: str,
        config,
        top_k: int | None = None,
        score_threshold: float | None = None,
        filenames: list[str] | None = None,
        vectorstore_id: str | None = None,
    ) -> VectorSearchResult:
        effective_top_k = top_k if top_k is not None else config.vector_search.top_k
        effective_threshold = (
            score_threshold if score_threshold is not None else config.vector_search.score_threshold
        )
        collection = self._collection(config, config.vector_search.index_name)
        normalized_filenames = _normalize_filenames(filenames)
        where = None
        if normalized_filenames and self._collection_has_any_filename(
            collection, normalized_filenames
        ):
            if len(normalized_filenames) == 1:
                where = {"filename": normalized_filenames[0]}
            else:
                where = {"filename": {"$in": normalized_filenames}}
        query_kwargs = {
            "query_texts": [query],
            "n_results": effective_top_k,
            "include": ["documents", "metadatas", "distances"],
        }
        if where is not None:
            query_kwargs["where"] = where
        result = collection.query(**query_kwargs)

        hits: list[VectorSearchHit] = []
        documents = result.get("documents", [[]])[0]
        metadatas = result.get("metadatas", [[]])[0]
        distances = result.get("distances", [[]])[0]

        for document, metadata, distance in zip(documents, metadatas, distances, strict=False):
            score = 1.0 / (1.0 + (distance or 0.0))
            if effective_threshold is not None and score < effective_threshold:
                continue
            hits.append(
                VectorSearchHit(
                    document=document,
                    metadata=metadata or {},
                    score=score,
                )
            )

        return VectorSearchResult(query=query, results=hits[:effective_top_k])

    def tool_name(self) -> str:
        return "vector_search"
