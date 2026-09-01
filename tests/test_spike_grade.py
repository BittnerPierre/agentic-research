"""Tests for the spike quality/grounding/spec grader (issue #196)."""

import json

import pytest

from evaluations import spike_grade


def test_corpus_from_sources_labels_with_ids():
    sources = [
        {"source_id": "S1", "topic": "mips", "file_name": "mips.txt", "content": "MIPS."},
        {"source_id": "S2", "topic": "ann", "file_name": "ann.txt", "content": "ANN."},
    ]
    corpus = spike_grade.corpus_from_sources(sources)
    assert "### [S1] mips" in corpus
    assert "(source: mips.txt)" in corpus
    assert "MIPS." in corpus
    assert "### [S2] ann" in corpus


def test_find_run_dirs_accepts_dir_and_parent(tmp_path):
    run = tmp_path / "runs" / "r1"
    run.mkdir(parents=True)
    (run / "stats.json").write_text("{}", encoding="utf-8")

    assert spike_grade.find_run_dirs([str(tmp_path)]) == [run]
    assert spike_grade.find_run_dirs([str(run)]) == [run]


def test_spike_overall_quality_first_and_grounding_gate():
    # Strong scores but ungrounded -> capped (the report ignored the sources).
    capped = spike_grade.spike_overall(95.0, rag_average=0.2, spec_100=90.0, groundedness=0.2)
    assert capped <= 50.0
    # Well grounded -> the weighted composite stands.
    full = spike_grade.spike_overall(80.0, rag_average=0.9, spec_100=80.0, groundedness=0.9)
    assert full > 70.0


class _Dump:
    def __init__(self, data):
        self._data = data

    def model_dump(self):
        return self._data


class _Quality:
    def __init__(self):
        self.grades = _Dump({"format": "A", "grounding": "A", "agenda": "B", "usability": "A"})
        self.judgment = "PASS"
        self.reasoning = "ok"


@pytest.mark.asyncio
async def test_grade_run_writes_grade_json(monkeypatch, tmp_path):
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    (output_dir / "report.md").write_text("# R\n\nContenu [S1].", encoding="utf-8")

    run = tmp_path / "runs" / "r1"
    run.mkdir(parents=True)
    (run / "stats.json").write_text(
        json.dumps({"report_file": "report.md", "query": "Q"}), encoding="utf-8"
    )
    (run / "sources.json").write_text(
        json.dumps([{"source_id": "S1", "topic": "t", "file_name": "f.txt", "content": "c"}]),
        encoding="utf-8",
    )

    captured = {}

    async def fake_triad(report, corpus, query, judge_model="openai/gpt-4.1-mini"):
        captured["corpus"] = corpus
        return _Dump(
            {
                "groundedness": 0.9,
                "context_relevance": 0.8,
                "answer_relevance": 0.7,
                "average": 0.8,
            }
        )

    async def fake_quality(report, corpus, query, judge_model):
        return _Quality()

    async def fake_spec(report, syllabus, raw_notes, judge_model="openai/gpt-4.1-mini"):
        captured["syllabus"] = syllabus
        captured["spec_context"] = raw_notes
        return _Dump({"score_100": 82.0, "violations": [], "unauthorized_sources": []})

    monkeypatch.setattr(spike_grade, "evaluate_rag_triad", fake_triad)
    monkeypatch.setattr(spike_grade, "evaluate_quality", fake_quality)
    monkeypatch.setattr(spike_grade, "evaluate_spec_compliance", fake_spec)
    monkeypatch.setattr(spike_grade, "quality_score_100", lambda q: 90.0)

    grade = await spike_grade.grade_run(run, "openai/gpt-4.1", str(output_dir))

    # Every judge is fed the retrieved corpus, not the report's own notes.
    assert "### [S1] t" in captured["corpus"]
    assert "### [S1] t" in captured["spec_context"]
    assert captured["syllabus"] == "Q"

    assert grade["quality"]["quality_100"] == 90.0
    assert grade["spec"]["score_100"] == 82.0
    assert grade["rag_triad"]["average"] == 0.8
    assert grade["overall_quality_100"] > 70.0  # well grounded

    written = json.loads((run / "grade.json").read_text(encoding="utf-8"))
    assert written["judge_model"] == "openai/gpt-4.1"
    assert written["quality"]["grades"]["grounding"] == "A"


@pytest.mark.asyncio
async def test_grade_run_skips_when_report_missing(monkeypatch, tmp_path):
    run = tmp_path / "runs" / "r1"
    run.mkdir(parents=True)
    (run / "stats.json").write_text(json.dumps({"report_file": "nope.md"}), encoding="utf-8")
    (run / "sources.json").write_text(json.dumps([]), encoding="utf-8")

    async def boom(*a, **k):  # pragma: no cover - must not be called
        raise AssertionError("should not grade without a report")

    monkeypatch.setattr(spike_grade, "evaluate_rag_triad", boom)
    monkeypatch.setattr(spike_grade, "evaluate_quality", boom)
    monkeypatch.setattr(spike_grade, "evaluate_spec_compliance", boom)
    assert await spike_grade.grade_run(run, "openai/gpt-4.1-mini", str(tmp_path / "output")) is None
