"""Vector store backend implementations."""

from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Protocol

from openai import OpenAI

from pathlib import Path

from .knowledge_db import KnowledgeDBManager
from .models import UploadResult
from .vector_search import VectorSearchResult, create_document, get_vector_search_backend
from .vector_store_manager import VectorStoreManager
from .vector_store_utils import read_local_file, resolve_inputs_to_entries

logger = logging.getLogger(__name__)


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
    ) -> VectorSearchResult:
        """Search over locally indexed documents."""

    def tool_name(self) -> str:
        """Return the tool name used in trajectories."""


class VectorStoreRegistry:
    _store_ids: dict[tuple[str, str], str] = {}

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
            files_uploaded.append({"filename": entry.filename, "doc_id": doc_id, "status": "indexed"})
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
    ) -> VectorSearchResult:
        from . import vector_search as vector_search_module

        backend = vector_search_module.get_vector_search_backend(config)
        effective_top_k = top_k if top_k is not None else config.vector_search.top_k
        effective_threshold = (
            score_threshold if score_threshold is not None else config.vector_search.score_threshold
        )
        hits = backend.query(
            query=query, top_k=effective_top_k, score_threshold=effective_threshold
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
                    f"Réutilisation du fichier OpenAI existant: {entry.filename} -> {entry.openai_file_id}"
                )
                files_uploaded.append(
                    {"filename": entry.filename, "file_id": entry.openai_file_id, "status": "reused"}
                )
                files_to_attach.append((entry.openai_file_id, entry.filename))
                reuse_count += 1
            else:
                try:
                    logger.info(f"Upload du nouveau fichier: {entry.filename}")
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
                    logger.error(f"Erreur upload {entry.filename}: {e}")
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
                    vector_store_id=vector_store_id, file_id=file_id
                )
                logger.info(
                    f"Fichier attaché au vector store: {filename} (status: {vector_store_file.status})"
                )
                return {
                    "filename": filename,
                    "file_id": file_id,
                    "vector_store_file_id": vector_store_file.id,
                    "status": vector_store_file.status,
                    "success": True,
                }
            except Exception as e:
                logger.error(f"Erreur attachement {filename}: {e}")
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
    ) -> VectorSearchResult:
        raise ValueError("vector_search is only available for provider=local")

    def tool_name(self) -> str:
        return "file_search"


def get_vector_backend(config) -> VectorBackend:
    provider = config.vector_search.provider
    if provider == "local":
        return LocalVectorBackend()
    if provider == "openai":
        return OpenAIVectorBackend()
    raise ValueError(f"Unknown vector_search.provider: {provider}")
