"""Assembly step (D3) — stitch chapters into the final report, programmatically.

No LLM here: ordering, headings, and the Sources section are deterministic. The
Sources section is built from the [S#] ids actually cited across chapters, which
is our source-traceability deliverable.
"""

from __future__ import annotations

import re

from ..agents.schemas import Chapter, ReportOutline, SourceDocument

_SID_RE = re.compile(r"\[(S\d+)\]")


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
        parts.append(f"## {chapter.title}\n\n{body}")
        bodies.append(body)

    parts.append(build_sources_section(sources, cited_source_ids(bodies)))
    return "\n\n".join(parts)
