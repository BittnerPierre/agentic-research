"""Decomposed writer pipeline (issue #196).

Entry point used by deep_research_manager when ``writer_strategy == "decomposed"``:

    D0 aggregate (code) -> D1 outline (LLM) -> D2 chapters (LLM, parallel)
    -> D3 assemble (code) -> ReportData

Each step is small and isolated. The heavy monolithic writer is replaced by
short, bounded calls so large hybrid models on the Spark cluster stay fast and
reliable, and the report carries [S#] source traceability.
"""

from __future__ import annotations

from ..agents.schemas import ReportData, ReportOutline, ResearchInfo
from ..agents.utils import parse_writer_markdown
from ..config import get_config
from .aggregate import aggregate_sources, render_corpus
from .assemble import assemble_report
from .chapters import write_chapters
from .outline import build_outline


async def write_report_decomposed(
    query: str,
    agenda: str,
    search_results: list[str | None],
    research_info: ResearchInfo,
    usage_sink=None,
) -> ReportData:
    """Run the decomposed writer and return a ReportData (same shape as monolithic).

    ``usage_sink`` is an optional callable ``(run_result, phase) -> None`` used by
    the manager to accumulate token usage (phase ``"writing"``).
    """
    config = get_config()

    # D0 — programmatic aggregation (no LLM, no MCP).
    sources = aggregate_sources(search_results)
    corpus = render_corpus(sources)

    # D1 — structured outline (reasoning step, with deterministic fallback).
    outline = await build_outline(query, agenda, sources, research_info, usage_sink)

    # Writing budget: cap the number of chapters if configured.
    max_chapters = config.agents.writer_max_chapters
    if max_chapters is not None and len(outline.chapters) > max_chapters:
        outline = ReportOutline(title=outline.title, chapters=outline.chapters[:max_chapters])

    # D2 — parallel chapter drafting. Only require [S#] citations when we have sources.
    chapters = await write_chapters(
        outline,
        corpus,
        research_info,
        require_citation=bool(sources),
        usage_sink=usage_sink,
    )

    # D3 — deterministic assembly + Sources section.
    markdown = assemble_report(outline, chapters, sources)

    # Reuse the existing markdown -> ReportData conversion for a consistent output.
    return parse_writer_markdown(markdown, query)
