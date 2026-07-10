"""Decomposed writer pipeline (issue #196).

Entry point used by deep_research_manager when ``writer_strategy == "decomposed"``:

    D0 aggregate (code) -> D1 outline (LLM) -> D2 chapters (LLM, parallel)
    -> D3 assemble (code) -> ReportData

Each step is small and isolated. The heavy monolithic writer is replaced by
short, bounded calls so large hybrid models on the Spark cluster stay fast and
reliable, and the report carries [S#] source traceability.
"""

from __future__ import annotations

import time

from ..agents.schemas import ReportData, ResearchInfo
from ..agents.utils import parse_writer_markdown
from ..config import get_config
from .aggregate import aggregate_sources, render_corpus
from .assemble import assemble_report, grounding_metrics
from .chapters import write_chapters
from .outline import build_outline


async def write_report_decomposed(
    query: str,
    agenda: str,
    search_results: list[str | None],
    research_info: ResearchInfo,
    usage_sink=None,
    metrics: dict | None = None,
) -> ReportData:
    """Run the decomposed writer and return a ReportData (same shape as monolithic).

    ``usage_sink`` is an optional callable ``(run_result, phase) -> None`` used by
    the manager to accumulate token usage (phase ``"writing"``).

    ``metrics`` is an optional dict the pipeline fills with per-step timing and
    grounding stats (used by the benchmark sidecar).
    """
    config = get_config()

    # D0 — programmatic aggregation (no LLM, no MCP).
    sources = aggregate_sources(search_results)
    corpus = render_corpus(sources)

    # D1 — structured outline (reasoning step, with deterministic fallback).
    outline_start = time.perf_counter()
    outline = await build_outline(query, agenda, sources, research_info, usage_sink)
    outline_seconds = time.perf_counter() - outline_start

    # Writing budget: cap the number of chapters if configured. Use model_copy
    # so short_summary / follow_up_questions survive the truncation (else the
    # ReportData contract silently regresses whenever the cap fires).
    max_chapters = config.agents.writer_max_chapters
    if max_chapters is not None and len(outline.chapters) > max_chapters:
        outline = outline.model_copy(update={"chapters": outline.chapters[:max_chapters]})

    # D2 — parallel chapter drafting. Only require [S#] citations when we have sources.
    chapters_start = time.perf_counter()
    chapters, chapter_durations, chapter_calls = await write_chapters(
        outline,
        corpus,
        research_info,
        require_citation=bool(sources),
        usage_sink=usage_sink,
    )
    chapters_wall = time.perf_counter() - chapters_start

    # D3 — deterministic assembly + Sources section.
    markdown = assemble_report(outline, chapters, sources)

    # Honest LLM-call count for the benchmark: 1 outline call + chapter attempts
    # (initial + guardrail retries). The monolithic path is a single call, so
    # this keeps agent_calls comparable across strategies.
    llm_calls = 1 + chapter_calls

    if metrics is not None:
        total_chapter_seconds = sum(chapter_durations)
        metrics.update(
            {
                "outline_title": outline.title,
                "outline_seconds": outline_seconds,
                "n_chapters": len(outline.chapters),
                "chapter_seconds": chapter_durations,
                "chapters_wall_seconds": chapters_wall,
                # >1 => chapters genuinely overlapped (vLLM batching);
                # ~1 => serialized (e.g. llama.cpp switching models).
                "concurrency_ratio": (
                    total_chapter_seconds / chapters_wall if chapters_wall > 0 else None
                ),
                "llm_calls": llm_calls,
                "grounding": grounding_metrics(chapters, sources),
            }
        )

    # Reuse parse_writer_markdown for title/filename/summary fallback, then let
    # the outline's own summary + follow-up questions win when present, so the
    # decomposed path fills the same ReportData contract as the monolithic one.
    report = parse_writer_markdown(markdown, query)
    updates: dict = {}
    if outline.short_summary.strip():
        updates["short_summary"] = outline.short_summary.strip()
    if outline.follow_up_questions:
        updates["follow_up_questions"] = list(outline.follow_up_questions)
    return report.model_copy(update=updates) if updates else report
