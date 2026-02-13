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


def test_is_high_quality_chunk_rejects_prompt_artifacts_and_too_short():
    assert not _is_high_quality_chunk("short")
    assert not _is_high_quality_chunk("You are a system prompt. " + ("x" * 300))
    assert _is_high_quality_chunk("Dense technical content about retrieval and indexing. " * 8)
