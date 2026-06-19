"""Tests for the deterministic assembly + traceability (issue #196, brique 2)."""

from src.agents.schemas import Chapter, ReportOutline, SourceDocument
from src.report_writer.assemble import (
    assemble_report,
    build_sources_section,
    cited_source_ids,
)
from src.report_writer.outline import fallback_outline


def _src(sid, topic, file_name):
    return SourceDocument(source_id=sid, file_name=file_name, topic=topic, content="x")


def test_cited_source_ids_unique_in_order():
    texts = ["MIPS [S2] and ANN [S1].", "Again [S2], plus [S3]."]
    assert cited_source_ids(texts) == ["S2", "S1", "S3"]


def test_build_sources_section_lists_only_cited():
    sources = [_src("S1", "mips", "mips.txt"), _src("S2", "ann", "ann.txt")]
    section = build_sources_section(sources, ["S2"])
    assert "## Sources" in section
    assert "- [S2] ann — ann.txt" in section
    assert "S1" not in section


def test_build_sources_section_falls_back_to_all_when_nothing_cited():
    sources = [_src("S1", "mips", "mips.txt"), _src("S2", "ann", "ann.txt")]
    section = build_sources_section(sources, [])
    assert "- [S1] mips — mips.txt" in section
    assert "- [S2] ann — ann.txt" in section


def test_assemble_report_orders_chapters_and_adds_sources():
    outline = ReportOutline(
        title="Mémoire externe des agents LLM",
        chapters=[
            Chapter(title="MIPS", objective="o1"),
            Chapter(title="ReWOO", objective="o2"),
        ],
    )
    chapters = [
        (outline.chapters[0], "MIPS résout la recherche [S1]."),
        (outline.chapters[1], "ReWOO planifie [S2]."),
    ]
    sources = [_src("S1", "mips", "mips.txt"), _src("S2", "rewoo", "rewoo.txt")]

    report = assemble_report(outline, chapters, sources)

    assert report.startswith("# Mémoire externe des agents LLM")
    assert report.index("## MIPS") < report.index("## ReWOO") < report.index("## Sources")
    assert "- [S1] mips — mips.txt" in report
    assert "- [S2] rewoo — rewoo.txt" in report


def test_assemble_report_skips_empty_chapter_bodies():
    outline = ReportOutline(
        title="T",
        chapters=[Chapter(title="Empty", objective="o"), Chapter(title="Full", objective="o")],
    )
    chapters = [(outline.chapters[0], "   "), (outline.chapters[1], "Content [S1].")]
    sources = [_src("S1", "topic", "f.txt")]

    report = assemble_report(outline, chapters, sources)

    assert "## Empty" not in report
    assert "## Full" in report


def test_fallback_outline_single_chapter_with_all_sources():
    sources = [_src("S1", "a", "a.txt"), _src("S2", "b", "b.txt")]
    outline = fallback_outline("Sujet de recherche\nligne 2", sources)

    assert outline.title == "Sujet de recherche"
    assert len(outline.chapters) == 1
    assert outline.chapters[0].source_ids == ["S1", "S2"]
