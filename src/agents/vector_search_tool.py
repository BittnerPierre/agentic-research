import re

from agents import RunContextWrapper, function_tool

from ..config import get_config
from ..dataprep.mcp_functions import vector_search as _vector_search
from .schemas import ResearchInfo

DEFAULT_RETRIEVE_CANDIDATES = 80
MAX_CHARS_PER_CHUNK = 1500
MIN_CHARS_PER_CHUNK = 200
MAX_CHUNKS_PER_DOCUMENT = 3

_PROMPT_ARTIFACT_RE = re.compile(
    r"(RECOMMENDED_PROMPT_PREFIX|You are a|system prompt|tool_call|BEGIN|END)",
    re.IGNORECASE,
)


def _normalize_query(query: str) -> str:
    return " ".join(query.split()).strip()


def _normalize_document_text(text: str) -> str:
    lines = [line.strip() for line in text.splitlines()]
    cleaned_lines = [line for line in lines if line]
    cleaned = "\n".join(cleaned_lines)
    return cleaned[:MAX_CHARS_PER_CHUNK]


def _doc_key(metadata: dict, document: str) -> tuple[str, str]:
    document_id = str(metadata.get("document_id") or metadata.get("filename") or "unknown")
    chunk_id = str(
        metadata.get("chunk_index")
        if metadata.get("chunk_index") is not None
        else metadata.get("chunk_id") or hash(document[:128])
    )
    return (document_id, chunk_id)


@function_tool
async def vector_search(
    wrapper: RunContextWrapper[ResearchInfo],
    query: str,
    top_k: int | None = None,
    score_threshold: float | None = None,
) -> dict:
    return await vector_search_impl(
        wrapper=wrapper,
        query=query,
        top_k=top_k,
        score_threshold=score_threshold,
    )


async def vector_search_impl(
    wrapper: RunContextWrapper[ResearchInfo],
    query: str,
    top_k: int | None = None,
    score_threshold: float | None = None,
) -> dict:
    config = get_config()
    if wrapper.context.vector_store_name:
        config.vector_search.index_name = wrapper.context.vector_store_name

    normalized_query = _normalize_query(query)
    final_top_k = top_k if top_k is not None else config.vector_search.top_k
    retrieve_top_k = max(final_top_k, DEFAULT_RETRIEVE_CANDIDATES)

    result = _vector_search(
        query=normalized_query,
        config=config,
        top_k=retrieve_top_k,
        score_threshold=score_threshold,
    )

    seen: set[tuple[str, str]] = set()
    per_doc_count: dict[str, int] = {}
    filtered_results: list[dict] = []

    for hit in result.results:
        metadata = dict(hit.metadata or {})
        document = _normalize_document_text(hit.document or "")

        if len(document) < MIN_CHARS_PER_CHUNK:
            continue
        if _PROMPT_ARTIFACT_RE.search(document):
            continue

        key = _doc_key(metadata, document)
        if key in seen:
            continue
        seen.add(key)

        doc_bucket = key[0]
        current_doc_count = per_doc_count.get(doc_bucket, 0)
        if current_doc_count >= MAX_CHUNKS_PER_DOCUMENT:
            continue
        per_doc_count[doc_bucket] = current_doc_count + 1

        filtered_results.append(
            {
                "document": document,
                "metadata": metadata,
                "score": hit.score,
            }
        )
        if len(filtered_results) >= final_top_k:
            break

    return {
        "query": normalized_query,
        "results": filtered_results,
    }
