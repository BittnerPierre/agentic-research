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


def _query_terms(query: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", query.lower())


def _build_paraphrase_variants(query: str, max_variants: int) -> list[str]:
    variants: list[str] = []
    compact = _normalize_query(re.sub(r"[()]+", " ", query))
    if compact and compact.lower() != query.lower():
        variants.append(compact)

    terms = _query_terms(query)
    if terms:
        intent = f"{' '.join(terms)} definition architecture implementation tradeoffs"
        intent = _normalize_query(intent)
        if intent.lower() != query.lower() and intent not in variants:
            variants.append(intent)

    return variants[: max(0, max_variants)]


def _build_hyde_variants(query: str, max_variants: int) -> list[str]:
    if max_variants <= 0:
        return []
    hyde = (
        "Hypothetical answer: "
        f"{query}. Explain key definitions, implementation details, tradeoffs, and examples."
    )
    return [_normalize_query(hyde)]


def _build_retrieval_queries(query: str, config) -> list[str]:
    primary = _normalize_query(query)
    mode = getattr(config.vector_search, "query_expansion_mode", "none")
    max_variants = int(getattr(config.vector_search, "query_expansion_max_variants", 2))

    variants: list[str] = []
    if mode == "paraphrase_lite":
        variants = _build_paraphrase_variants(primary, max_variants=max_variants)
    elif mode == "hyde_lite":
        variants = _build_hyde_variants(primary, max_variants=max_variants)

    # Keep order and dedupe.
    seen: set[str] = set()
    out: list[str] = []
    for candidate in [primary, *variants]:
        normalized = _normalize_query(candidate)
        if not normalized:
            continue
        key = normalized.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(normalized)
    return out


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

    retrieval_queries = _build_retrieval_queries(query, config)
    normalized_query = retrieval_queries[0] if retrieval_queries else _normalize_query(query)
    final_top_k = top_k if top_k is not None else config.vector_search.top_k
    retrieve_top_k = max(final_top_k, DEFAULT_RETRIEVE_CANDIDATES)

    all_hits = []
    for retrieval_query in retrieval_queries:
        result = _vector_search(
            query=retrieval_query,
            config=config,
            top_k=retrieve_top_k,
            score_threshold=score_threshold,
        )
        all_hits.extend(result.results)

    seen: set[tuple[str, str]] = set()
    per_doc_count: dict[str, int] = {}
    filtered_results: list[dict] = []

    for hit in sorted(all_hits, key=lambda item: item.score, reverse=True):
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
        "effective_queries": retrieval_queries,
        "results": filtered_results,
    }
