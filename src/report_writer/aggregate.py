"""Programmatic aggregation of search results (issue #196, brique 1).

This replaces the writer's MCP ``read_multiple_files`` + verbatim "Raw Notes"
step. Concatenating already-compact search summaries does not need an LLM, so we
do it in plain Python at the output of the search phase. The writer then works
from stable ``[S#]`` source ids, which also gives us source traceability for
free.
"""

from __future__ import annotations

import os
import re

from ..agents.schemas import SourceDocument

# Inline retrieval citations emitted by the file_search agent, e.g. "[doc_id:3]".
# Our own "[S1]" source ids have no ":<digits>" and are intentionally not matched.
_CITATION_RE = re.compile(r"\[([^\[\]]+?:\d+)\]")


def topic_from_filename(file_name: str) -> str:
    """Derive a human-readable topic from a search-result filename.

    Filenames are the slugified search term (see file_search_prompt.md), e.g.
    ``multi_agent_orchestration.txt`` -> ``multi agent orchestration``.
    """
    stem = os.path.splitext(os.path.basename(file_name))[0]
    return stem.replace("_", " ").strip()


def extract_doc_ids(content: str) -> list[str]:
    """Return unique ``document_id:chunk_index`` citations, in order of appearance.

    Small models often omit these despite the prompt asking for them, so callers
    must treat an empty list as normal rather than an error.
    """
    seen: dict[str, None] = {}
    for match in _CITATION_RE.findall(content):
        seen.setdefault(match.strip(), None)
    return list(seen)


def aggregate_sources(file_paths: list[str | None]) -> list[SourceDocument]:
    """Read search-result files into ordered ``SourceDocument`` records.

    Pure I/O + parsing — no LLM, no MCP.

    - ``None`` entries (failed individual searches) and missing/empty files are
      skipped so a partial search phase still yields a usable corpus.
    - Exact-duplicate contents are dropped: the same summary often surfaces from
      several queries. Near-duplicates are deliberately kept (judging similarity
      is subjective and out of scope for this spike — KISS).
    - ``source_id`` is assigned ``S1``, ``S2``, ... in input order, after dedup,
      so ids stay contiguous regardless of skipped entries.
    """
    sources: list[SourceDocument] = []
    seen_contents: set[str] = set()

    for path in file_paths:
        if not path or not os.path.isfile(path):
            continue
        with open(path, encoding="utf-8") as fh:
            content = fh.read().strip()
        if not content or content in seen_contents:
            continue
        seen_contents.add(content)
        sources.append(
            SourceDocument(
                source_id=f"S{len(sources) + 1}",
                file_name=os.path.basename(path),
                topic=topic_from_filename(path),
                content=content,
                doc_ids=extract_doc_ids(content),
            )
        )

    return sources


def render_corpus(sources: list[SourceDocument]) -> str:
    """Render the aggregated corpus as one labelled markdown block.

    This is the programmatic "concatenation" handed to chapter writers; each
    source is prefixed with its ``[S#]`` id so the model can cite it inline.
    """
    blocks = [
        f"### [{src.source_id}] {src.topic}\n(source: {src.file_name})\n\n{src.content}"
        for src in sources
    ]
    return "\n\n".join(blocks)
