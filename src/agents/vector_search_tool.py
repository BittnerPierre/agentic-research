import logging
import os
import re
from typing import Any

from openai import OpenAI

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
logger = logging.getLogger(__name__)

_DOMAIN_HINT_KEYWORDS: dict[str, tuple[str, ...]] = {
    "financial research": (
        "annual report",
        "10-k",
        "10q",
        "balance sheet",
        "income statement",
        "cash flow",
        "ebitda",
        "guidance",
        "sec filing",
        "earnings",
        "valuation",
    ),
    "legal analysis": (
        "contract",
        "regulation",
        "compliance",
        "law",
        "gdpr",
        "policy",
        "terms",
    ),
    "medical/health research": (
        "clinical",
        "patient",
        "diagnosis",
        "treatment",
        "trial",
        "healthcare",
        "drug",
        "medical",
    ),
    "software engineering research": (
        "api",
        "sdk",
        "python",
        "docker",
        "llm",
        "embedding",
        "vector search",
        "benchmark",
        "architecture",
    ),
}


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
    topic = _normalize_query(query)
    hyde = (
        f"{topic} is a set of practical methods used in real systems. "
        f"It typically combines core concepts, implementation patterns, tradeoffs, and concrete "
        f"use cases. Key points include what it is, how it works, when to apply it, and common pitfalls."
    )
    return [_normalize_query(hyde)]


def _infer_domain_hint(query: str) -> str:
    normalized = _normalize_query(query).lower()
    if not normalized:
        return "general research"
    for domain, keywords in _DOMAIN_HINT_KEYWORDS.items():
        if any(keyword in normalized for keyword in keywords):
            return domain
    return "general research"


def _resolve_domain_hint(query: str, domain_hint: str | None) -> tuple[str, str]:
    normalized_hint = _normalize_query(domain_hint or "")
    if normalized_hint:
        return normalized_hint, "agent_override"
    return _infer_domain_hint(query), "heuristic"


def _to_hyde_hypothesis(primary_query: str, candidate: str) -> str:
    text = _normalize_query(candidate).rstrip("?")
    if not text:
        return _build_hyde_variants(primary_query, 1)[0]
    if text.lower().startswith("hypothetical answer:"):
        text = _normalize_query(text.split(":", 1)[1])
    return text


def _resolve_dataprep_llm_endpoint(config) -> tuple[str, str | None, str | None]:
    llm_cfg = config.dataprep.llm
    model_spec = llm_cfg.model
    if isinstance(model_spec, str):
        return model_spec, None, None
    return model_spec.name, model_spec.base_url, model_spec.api_key


def _extract_json_array_of_queries(text: str) -> list[str]:
    # Be tolerant: model might include surrounding prose.
    start = text.find("[")
    end = text.rfind("]")
    if start == -1 or end == -1 or end < start:
        return []
    payload = text[start : end + 1]
    try:
        import json

        data = json.loads(payload)
    except Exception:
        return []
    if not isinstance(data, list):
        return []
    out: list[str] = []
    for item in data:
        if not isinstance(item, str):
            continue
        normalized = _normalize_query(item)
        if normalized:
            out.append(normalized)
    return out


def _build_llm_rewrite_queries(
    query: str,
    *,
    mode: str,
    max_variants: int,
    config: Any,
    domain_hint: str | None = None,
) -> list[str]:
    if max_variants <= 0:
        return []
    if not getattr(config.dataprep.llm, "enabled", True):
        logger.warning(
            "LLM rewrite disabled (dataprep.llm.enabled=false); heuristic fallback will be used."
        )
        return []

    model, base_url, api_key = _resolve_dataprep_llm_endpoint(config)
    resolved_api_key = api_key or os.getenv(config.dataprep.llm.api_key_env) or "dummy"
    client = OpenAI(
        base_url=base_url,
        api_key=resolved_api_key,
        timeout=float(config.dataprep.llm.timeout_seconds),
    )

    style = "paraphrases that preserve intent" if mode == "paraphrase_lite" else "hypothetical answer queries"
    resolved_hint, _ = _resolve_domain_hint(query, domain_hint)
    if mode == "hyde_lite":
        task_line = (
            f"Task: Produce up to {max_variants} hypothetical answer passages for the input query."
        )
        rules = (
            "Rules:\n"
            "- Write each output as a short declarative answer snippet (not a question).\n"
            "- Make it realistic for documents in this domain.\n"
            "- Keep them specific and retrieval-oriented.\n"
            "- Do not output explanations.\n"
            "- Return ONLY a JSON array of strings.\n"
        )
    else:
        task_line = f"Task: Produce up to {max_variants} {style} for the input query."
        rules = (
            "Rules:\n"
            "- Keep them specific and retrieval-oriented.\n"
            "- Do not output explanations.\n"
            "- Return ONLY a JSON array of strings.\n"
        )

    prompt = (
        "You are a helpful expert research assistant.\n"
        f"Domain context hint: {resolved_hint}.\n"
        "You generate vector retrieval queries.\n"
        f"{task_line}\n"
        f"{rules}"
        f'Input query: "{_normalize_query(query)}"'
    )

    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=float(config.dataprep.llm.temperature),
        max_tokens=int(config.dataprep.llm.max_tokens),
    )
    content = (response.choices[0].message.content or "").strip()
    return _extract_json_array_of_queries(content)[:max_variants]


def _build_retrieval_queries(
    query: str,
    *,
    rewrite_query: bool = False,
    rewrite_mode: str = "paraphrase_lite",
    max_variants: int = 2,
    config: Any | None = None,
    domain_hint: str | None = None,
) -> list[str]:
    primary = _normalize_query(query)
    mode = rewrite_mode if rewrite_query else "none"

    variants: list[str] = []
    if mode == "paraphrase_lite":
        if config is not None:
            try:
                variants = _build_llm_rewrite_queries(
                    primary,
                    mode=mode,
                    max_variants=max_variants,
                    config=config,
                    domain_hint=domain_hint,
                )
            except Exception:
                logger.warning(
                    "LLM paraphrase rewrite failed; using heuristic fallback.",
                    exc_info=True,
                )
                variants = _build_paraphrase_variants(primary, max_variants=max_variants)
        else:
            variants = _build_paraphrase_variants(primary, max_variants=max_variants)
    elif mode == "hyde_lite":
        if config is not None:
            try:
                variants = _build_llm_rewrite_queries(
                    primary,
                    mode=mode,
                    max_variants=max_variants,
                    config=config,
                    domain_hint=domain_hint,
                )
            except Exception:
                logger.warning(
                    "LLM HYDE rewrite failed; using heuristic fallback.",
                    exc_info=True,
                )
                variants = _build_hyde_variants(primary, max_variants=max_variants)
        else:
            variants = _build_hyde_variants(primary, max_variants=max_variants)
        # Enforce HYDE semantics even if the model returns plain paraphrases/questions.
        variants = [_to_hyde_hypothesis(primary, item) for item in variants[:max_variants]]

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
    domain_hint: str | None = None,
) -> dict:
    return await vector_search_impl(
        wrapper=wrapper,
        query=query,
        domain_hint=domain_hint,
    )


async def vector_search_impl(
    wrapper: RunContextWrapper[ResearchInfo],
    query: str,
    domain_hint: str | None = None,
) -> dict:
    config = get_config()
    if wrapper.context.vector_store_name:
        config.vector_search.index_name = wrapper.context.vector_store_name

    rewrite_mode = getattr(config.agents, "file_search_rewrite_mode", "none")
    rewrite_enabled = rewrite_mode != "none"
    rewrite_max_variants = int(getattr(config.agents, "file_search_rewrite_max_variants", 2))
    if rewrite_mode == "hyde_lite":
        # Keep HYDE strictly mono-variant for predictable context usage and latency.
        rewrite_max_variants = 1
    resolved_hint, hint_source = _resolve_domain_hint(query, domain_hint)
    retrieval_queries = _build_retrieval_queries(
        query,
        rewrite_query=rewrite_enabled,
        rewrite_mode=rewrite_mode,
        max_variants=rewrite_max_variants,
        config=config,
        domain_hint=resolved_hint,
    )
    normalized_query = retrieval_queries[0] if retrieval_queries else _normalize_query(query)
    rewrite_applied = len(retrieval_queries) > 1
    effective_rewrite_mode = rewrite_mode if rewrite_applied else "none"
    final_top_k = (
        config.agents.file_search_top_k
        if config.agents.file_search_top_k is not None
        else config.vector_search.top_k
    )
    score_threshold = (
        config.agents.file_search_score_threshold
        if config.agents.file_search_score_threshold is not None
        else config.vector_search.score_threshold
    )
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

    if logger.isEnabledFor(logging.INFO):
        kept_scores = [result["score"] for result in filtered_results]
        kept_max = max(kept_scores) if kept_scores else None
        kept_min = min(kept_scores) if kept_scores else None
        logger.info(
            "vector_search diagnostics | query=%s | effective_queries=%s | rewrite_mode=%s "
            "| top_k=%s | score_threshold=%s | hits_total=%s | hits_kept=%s | unique_docs=%s "
            "| kept_score_range=%s..%s | domain_hint=%s (%s)",
            normalized_query,
            retrieval_queries,
            effective_rewrite_mode,
            final_top_k,
            score_threshold,
            len(all_hits),
            len(filtered_results),
            len(per_doc_count),
            kept_max,
            kept_min,
            resolved_hint,
            hint_source,
        )

    return {
        "query": normalized_query,
        "effective_queries": retrieval_queries,
        "observability": {
            "rewrite_requested": rewrite_enabled,
            "rewrite_applied": rewrite_applied,
            "rewrite_mode": effective_rewrite_mode,
            "rewrite_input_query": _normalize_query(query),
            "effective_queries_count": len(retrieval_queries),
            "rewrite_backend": "llm_openai_compatible"
            if rewrite_enabled and rewrite_applied
            else "none_or_fallback",
            "rewrite_domain_hint": resolved_hint,
            "rewrite_domain_hint_source": hint_source,
            "top_k": final_top_k,
            "score_threshold": score_threshold,
        },
        "results": filtered_results,
    }
