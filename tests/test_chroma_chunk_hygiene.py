"""Tests for Chroma ingestion cleaning and chunk quality gates."""

from __future__ import annotations

from src.dataprep.vector_backends import (
    _chunk_dense_text,
    _clean_for_rag,
    _is_high_quality_chunk,
)


def test_clean_for_rag_removes_front_matter_and_noise_sections():
    raw = """---
title: "Maximum inner"
source: "https://en.wikipedia.org/wiki/Maximum_inner_product_search"
content_length: 5259
---

# Maximum inner

Useful sentence about MIPS and ANN.

## References
1. noise
Retrieved from https://en.wikipedia.org/
"""
    cleaned = _clean_for_rag(raw)

    assert "title:" not in cleaned
    assert "content_length" not in cleaned
    assert "References" not in cleaned
    assert "Retrieved from" not in cleaned
    assert "Useful sentence about MIPS and ANN." in cleaned


def test_chunk_dense_text_builds_dense_chunks_and_quality_filter():
    text = (
        "Maximum inner product search is used for retrieval in vector databases.\n\n"
        "Approximate nearest neighbor methods reduce latency while preserving relevance.\n\n"
        "HNSW and IVF are common index choices for large-scale systems.\n\n"
        "Retrieved from https://example.com/"
    )
    cleaned = _clean_for_rag(text)
    chunks = _chunk_dense_text(cleaned, max_chars=220, overlap=40)

    assert chunks
    assert all(len(c) <= 220 for c in chunks)
    assert any("Approximate nearest neighbor methods" in c for c in chunks)
    assert all(_is_high_quality_chunk(c) for c in chunks)


def test_is_high_quality_chunk_rejects_only_structural_noise():
    """Regression #196 (pompon, 2026-07-15): the artifact-marker filter censored
    the very subject matter of technical corpora — chunks EXPLAINING system
    prompts ("system prompt", "You are a") or containing code examples were
    dropped at indexing, so retrieval could never surface them. Quality gating
    keeps only structural criteria (length, symbol ratio, link spam)."""
    assert not _is_high_quality_chunk("short")
    assert _is_high_quality_chunk(
        "A system prompt such as 'You are a helpful assistant' sets application "
        "rules that take priority over the user message. " * 3
    )
    assert _is_high_quality_chunk("Dense technical content about retrieval and indexing. " * 8)


def test_clean_for_rag_keeps_fenced_code_content():
    """Regression #196: code examples ARE content (Chroma usage, few-shot
    prompts lived only in fenced blocks and vanished from the index)."""
    raw = (
        "Vector stores in practice.\n\n"
        "```python\n"
        "chroma_collection = load_chroma(filename='report.pdf')\n"
        "chroma_collection.query(query_texts=query, n_results=10)\n"
        "```\n\n"
        "The collection supports similarity queries over embeddings.\n"
    )
    cleaned = _clean_for_rag(raw)

    assert "chroma_collection" in cleaned
    assert "similarity queries" in cleaned
    assert "```" not in cleaned
