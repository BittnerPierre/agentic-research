"""Tests for the programmatic source aggregation (issue #196, brique 1)."""

from src.report_writer.aggregate import (
    aggregate_sources,
    extract_doc_ids,
    render_corpus,
    topic_from_filename,
)


def _write(tmp_path, name: str, content: str) -> str:
    path = tmp_path / name
    path.write_text(content, encoding="utf-8")
    return str(path)


def test_topic_from_filename_humanizes_slug():
    assert (
        topic_from_filename("/tmp/x/multi_agent_orchestration.txt") == "multi agent orchestration"
    )
    assert topic_from_filename("rewoo.txt") == "rewoo"


def test_extract_doc_ids_unique_in_order_and_ignores_source_ids():
    content = "MIPS is fast [doc_a:0]. ANN scales [doc_b:12]. Repeat [doc_a:0]. See [S1]."
    assert extract_doc_ids(content) == ["doc_a:0", "doc_b:12"]


def test_extract_doc_ids_empty_when_no_citations():
    assert extract_doc_ids("Plain summary with no citations.") == []


def test_aggregate_assigns_contiguous_ids_and_parses_fields(tmp_path):
    paths = [
        _write(tmp_path, "mips.txt", "MIPS retrieves vectors [kb_1:3]."),
        _write(tmp_path, "ann_methods.txt", "ANN trades accuracy for speed."),
    ]
    sources = aggregate_sources(paths)

    assert [s.source_id for s in sources] == ["S1", "S2"]
    assert sources[0].file_name == "mips.txt"
    assert sources[0].topic == "mips"
    assert sources[0].content == "MIPS retrieves vectors [kb_1:3]."
    assert sources[0].doc_ids == ["kb_1:3"]
    assert sources[1].topic == "ann methods"
    assert sources[1].doc_ids == []


def test_aggregate_skips_none_missing_and_empty(tmp_path):
    paths = [
        None,
        str(tmp_path / "does_not_exist.txt"),
        _write(tmp_path, "blank.txt", "   \n  "),
        _write(tmp_path, "real.txt", "Real content."),
    ]
    sources = aggregate_sources(paths)

    assert [s.source_id for s in sources] == ["S1"]
    assert sources[0].file_name == "real.txt"


def test_aggregate_drops_exact_duplicate_content_keeps_ids_contiguous(tmp_path):
    paths = [
        _write(tmp_path, "a.txt", "Same chunk surfaced twice."),
        _write(tmp_path, "b.txt", "Same chunk surfaced twice."),
        _write(tmp_path, "c.txt", "A different chunk."),
    ]
    sources = aggregate_sources(paths)

    assert [s.source_id for s in sources] == ["S1", "S2"]
    assert sources[0].file_name == "a.txt"
    assert sources[1].file_name == "c.txt"


def test_render_corpus_labels_each_source_with_its_id(tmp_path):
    paths = [
        _write(tmp_path, "mips.txt", "MIPS content."),
        _write(tmp_path, "rewoo.txt", "ReWOO content."),
    ]
    corpus = render_corpus(aggregate_sources(paths))

    assert "### [S1] mips" in corpus
    assert "(source: mips.txt)" in corpus
    assert "MIPS content." in corpus
    assert "### [S2] rewoo" in corpus
    assert "ReWOO content." in corpus


def test_aggregate_empty_input_returns_empty_list():
    assert aggregate_sources([]) == []
