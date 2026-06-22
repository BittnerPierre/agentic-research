"""Tests for the RAG groundedness grader (issue #196)."""

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

    # parent dir scan + direct run dir both resolve to the run dir
    assert spike_grade.find_run_dirs([str(tmp_path)]) == [run]
    assert spike_grade.find_run_dirs([str(run)]) == [run]


class _FakeTriad:
    def model_dump(self):
        return {
            "groundedness": 0.9,
            "context_relevance": 0.8,
            "answer_relevance": 0.7,
            "average": 0.8,
            "reasoning": {},
        }


@pytest.mark.asyncio
async def test_grade_run_writes_grounding_json(monkeypatch, tmp_path):
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
        captured["query"] = query
        captured["judge_model"] = judge_model
        return _FakeTriad()

    monkeypatch.setattr(spike_grade, "evaluate_rag_triad", fake_triad)

    data = await spike_grade.grade_run(run, "openai/gpt-4.1", str(output_dir))

    assert data["average"] == 0.8
    # Grounding is judged against the retrieved corpus, not the report.
    assert "### [S1] t" in captured["corpus"]
    assert captured["query"] == "Q"
    assert captured["judge_model"] == "openai/gpt-4.1"
    written = json.loads((run / "grounding.json").read_text(encoding="utf-8"))
    assert written["groundedness"] == 0.9
    assert written["judge_model"] == "openai/gpt-4.1"


@pytest.mark.asyncio
async def test_grade_run_skips_when_report_missing(monkeypatch, tmp_path):
    run = tmp_path / "runs" / "r1"
    run.mkdir(parents=True)
    (run / "stats.json").write_text(json.dumps({"report_file": "nope.md"}), encoding="utf-8")
    (run / "sources.json").write_text(json.dumps([]), encoding="utf-8")

    async def fake_triad(*a, **k):  # pragma: no cover - must not be called
        raise AssertionError("should not grade without a report")

    monkeypatch.setattr(spike_grade, "evaluate_rag_triad", fake_triad)
    assert await spike_grade.grade_run(run, "openai/gpt-4.1-mini", str(tmp_path / "output")) is None
