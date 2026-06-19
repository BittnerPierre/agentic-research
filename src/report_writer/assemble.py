"""Assembly step (D3) — stitch chapters into the final report, programmatically.

No LLM here: ordering, headings, and the Sources section are deterministic. The
Sources section is built from the [S#] ids actually cited across chapters, which
is our source-traceability deliverable.
"""

from __future__ import annotations

import re

from ..agents.schemas import Chapter, ReportOutline, SourceDocument

_SID_RE = re.compile(r"\[(S\d+)\]")
_HEADING_RE = re.compile(r"^#{1,6}\s+(.*)$")


def _norm_heading(text: str) -> str:
    text = re.sub(r"[*_`#]", "", text.strip().lower())
    text = re.sub(r"\s+", " ", text)
    return text.strip(" :*-—")


def _strip_leading_title(body: str, title: str) -> str:
    """Drop a leading heading line that just repeats the chapter title.

    Chapter writers sometimes re-emit their own ``## Title`` despite the prompt
    asking them not to; the assembler already adds the heading, so without this
    the report shows the title twice in a row.
    """
    stripped = body.lstrip()
    lines = stripped.splitlines()
    if not lines:
        return body
    match = _HEADING_RE.match(lines[0].strip())
    if match and _norm_heading(match.group(1)) == _norm_heading(title):
        return "\n".join(lines[1:]).lstrip()
    return body


def cited_source_ids(texts: list[str]) -> list[str]:
    """Unique [S#] ids cited across the given texts, in order of first appearance."""
    seen: dict[str, None] = {}
    for text in texts:
        for sid in _SID_RE.findall(text):
            seen.setdefault(sid, None)
    return list(seen)


def build_sources_section(sources: list[SourceDocument], cited_ids: list[str]) -> str:
    """Render the '## Sources' section.

    Lists the cited sources for traceability; if nothing was cited (e.g. a small
    model dropped the [S#] tags), falls back to listing every source so the
    report still carries its provenance.
    """
    by_id = {s.source_id: s for s in sources}
    ids = cited_ids or [s.source_id for s in sources]
    lines = ["## Sources"]
    for sid in ids:
        src = by_id.get(sid)
        if src is not None:
            lines.append(f"- [{sid}] {src.topic} — {src.file_name}")
    return "\n".join(lines)


def assemble_report(
    outline: ReportOutline,
    chapters: list[tuple[Chapter, str]],
    sources: list[SourceDocument],
) -> str:
    """Assemble the final markdown report from drafted chapters."""
    parts = [f"# {outline.title}"]
    bodies: list[str] = []
    for chapter, body in chapters:
        body = (body or "").strip()
        if not body:
            continue
        body = _strip_leading_title(body, chapter.title)
        parts.append(f"## {chapter.title}\n\n{body}")
        bodies.append(body)

    parts.append(build_sources_section(sources, cited_source_ids(bodies)))
    return "\n\n".join(parts)


def grounding_metrics(chapters: list[tuple[Chapter, str]], sources: list[SourceDocument]) -> dict:
    """Cheap, objective grounding proxy (NOT a substitute for the RAG judge).

    Checks that chapters actually cite the retrieved sources by [S#]. It cannot
    tell whether a cited claim is truly supported — that is what the LLM
    groundedness judge over sources.json is for — but it's a free sanity signal.
    """
    bodies = [body for _, body in chapters if (body or "").strip()]
    cited = cited_source_ids(bodies)
    n_sources = len(sources)
    n_chapters = len([1 for _, body in chapters if (body or "").strip()])
    chapters_with_citation = sum(1 for body in bodies if _SID_RE.search(body))
    return {
        "n_sources": n_sources,
        "n_cited_sources": len(cited),
        "source_coverage": (len(cited) / n_sources) if n_sources else 0.0,
        "n_chapters": n_chapters,
        "chapters_with_citation": chapters_with_citation,
        "chapter_citation_rate": (chapters_with_citation / n_chapters) if n_chapters else 0.0,
    }
