"""Tests for the deterministic assembly + traceability (issue #196, brique 2)."""

from src.agents.schemas import Chapter, ReportOutline, SourceDocument
from src.report_writer.assemble import (
    _strip_wrapping_code_fence,
    assemble_report,
    build_sources_section,
    cited_source_ids,
    grounding_metrics,
)
from src.report_writer.outline import fallback_outline


def _src(sid, topic, file_name):
    return SourceDocument(source_id=sid, file_name=file_name, topic=topic, content="x")


def test_strip_wrapping_code_fence_unwraps_whole_body():
    body = "```markdown\n## Titre\n\nContenu [S1].\n```"
    assert _strip_wrapping_code_fence(body) == "## Titre\n\nContenu [S1]."


def test_strip_wrapping_code_fence_plain_fence():
    assert _strip_wrapping_code_fence("```\nTexte [S2].\n```") == "Texte [S2]."


def test_strip_wrapping_code_fence_leaves_unwrapped_body():
    body = "## Titre\n\nContenu normal [S1]."
    assert _strip_wrapping_code_fence(body) == body


def test_strip_wrapping_code_fence_preserves_inner_code_block():
    # A body that is NOT fully wrapped (real prose + an inner code block) is untouched.
    body = "Voici du code :\n\n```python\nprint('x')\n```\n\nFin [S1]."
    assert _strip_wrapping_code_fence(body) == body


def test_assemble_report_unwraps_fenced_chapter():
    outline = ReportOutline(title="Rapport", chapters=[Chapter(title="Ch1", objective="o")])
    chapters = [(Chapter(title="Ch1", objective="o"), "```markdown\nCorps [S1].\n```")]
    md = assemble_report(outline, chapters, [_src("S1", "t", "t.txt")])
    assert "```markdown" not in md
    assert "## Ch1\n\nCorps [S1]." in md


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


def test_assemble_report_strips_chapter_body_that_repeats_its_title():
    outline = ReportOutline(title="T", chapters=[Chapter(title="HNSW et FAISS", objective="o")])
    # The model re-emitted its own heading despite the prompt; assembler adds one too.
    body = "## HNSW et FAISS\n\nHNSW est un graphe navigable [S1]."
    report = assemble_report(outline, [(outline.chapters[0], body)], [_src("S1", "ann", "ann.txt")])

    # Exactly one occurrence of the heading, not two in a row.
    assert report.count("## HNSW et FAISS") == 1
    assert "HNSW est un graphe navigable [S1]." in report


def test_grounding_metrics_counts_citations_against_sources():
    sources = [_src("S1", "a", "a.txt"), _src("S2", "b", "b.txt"), _src("S3", "c", "c.txt")]
    chapters = [
        (Chapter(title="C1", objective="o"), "Cite [S1] et [S2]."),
        (Chapter(title="C2", objective="o"), "Pas de citation ici."),
        (Chapter(title="C3", objective="o"), "   "),  # empty -> ignored
    ]
    m = grounding_metrics(chapters, sources)

    assert m["n_sources"] == 3
    assert m["n_cited_sources"] == 2  # S1, S2 (S3 never cited)
    assert m["source_coverage"] == 2 / 3
    assert m["n_invalid_citations"] == 0
    assert m["n_chapters"] == 2  # empty chapter excluded
    assert m["chapters_with_citation"] == 1
    assert m["chapter_citation_rate"] == 1 / 2


def test_grounding_metrics_ignores_hallucinated_citations():
    # A model that cites [S99] (not in the retrieved corpus) must not inflate
    # coverage above 1.0 — the invalid id is dropped and surfaced separately.
    sources = [_src("S1", "a", "a.txt"), _src("S2", "b", "b.txt")]
    chapters = [
        (Chapter(title="C1", objective="o"), "Cite [S1], [S2] et un faux [S99]."),
    ]
    m = grounding_metrics(chapters, sources)

    assert m["n_cited_sources"] == 2  # S99 not counted
    assert m["source_coverage"] == 1.0  # never exceeds 1.0
    assert m["n_invalid_citations"] == 1  # S99 flagged


def test_fallback_outline_single_chapter_with_all_sources():
    sources = [_src("S1", "a", "a.txt"), _src("S2", "b", "b.txt")]
    outline = fallback_outline("Sujet de recherche\nligne 2", sources)

    assert outline.title == "Sujet de recherche"
    assert len(outline.chapters) == 1
    assert outline.chapters[0].source_ids == ["S1", "S2"]
