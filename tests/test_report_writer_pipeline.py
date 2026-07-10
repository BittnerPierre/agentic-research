"""Offline glue test for the decomposed writer pipeline (issue #196).

LLM calls (Runner.run) are stubbed so we validate the orchestration end to end
(D0 aggregate -> D1 outline -> D2 parallel chapters -> D3 assemble) without any
network: budget cap, citation guardrail retry, and traceability.
"""

import re

import pytest

from src.agents.schemas import Chapter, ReportOutline, ResearchInfo
from src.config import get_config
from src.report_writer import outline as outline_mod
from src.report_writer import pipeline as pipeline_mod


class _OutlineResult:
    def __init__(self, outline):
        self._outline = outline
        self.final_output = outline

    def final_output_as(self, _type):
        return self._outline


class _TextResult:
    def __init__(self, text):
        self.final_output = text


def _make_fake_runner(outline, chapter_text_fn, counter):
    class FakeRunner:
        @staticmethod
        async def run(agent, input_text, context=None, **kwargs):
            if agent.name == "outline_agent":
                counter["outline"] += 1
                return _OutlineResult(outline)
            counter["chapter"] += 1
            match = re.search(r"Chapitre à rédiger : (.+)", input_text)
            title = match.group(1).strip() if match else "?"
            return _TextResult(chapter_text_fn(title))

    return FakeRunner


def _research_info(tmp_path):
    return ResearchInfo(temp_dir=str(tmp_path), output_dir=str(tmp_path))


def _sources(tmp_path):
    p1 = tmp_path / "mips.txt"
    p1.write_text("MIPS retrieves vectors fast.", encoding="utf-8")
    p2 = tmp_path / "rewoo.txt"
    p2.write_text("ReWOO plans without observation.", encoding="utf-8")
    return [str(p1), str(p2)]


@pytest.mark.asyncio
async def test_pipeline_happy_path_assembles_chapters_and_sources(monkeypatch, tmp_path):
    outline = ReportOutline(
        title="Mémoire externe",
        chapters=[
            Chapter(title="MIPS", objective="o1", source_ids=["S1"]),
            Chapter(title="ReWOO", objective="o2", source_ids=["S2"]),
        ],
    )
    counter = {"outline": 0, "chapter": 0}

    def chapter_text(title):
        sid = "S1" if title == "MIPS" else "S2"
        return f"Contenu de {title} [{sid}]."

    fake = _make_fake_runner(outline, chapter_text, counter)
    monkeypatch.setattr(outline_mod, "Runner", fake)
    monkeypatch.setattr("src.report_writer.chapters.Runner", fake)

    report = await pipeline_mod.write_report_decomposed(
        "Mémoire externe des agents LLM", "agenda", _sources(tmp_path), _research_info(tmp_path)
    )

    assert counter["outline"] == 1
    assert counter["chapter"] == 2
    md = report.markdown_report
    assert "# Mémoire externe" in md
    assert md.index("## MIPS") < md.index("## ReWOO") < md.index("## Sources")
    assert "- [S1] mips — mips.txt" in md
    assert "- [S2] rewoo — rewoo.txt" in md


@pytest.mark.asyncio
async def test_pipeline_propagates_outline_summary_and_followups(monkeypatch, tmp_path):
    # The decomposed path must fill the same ReportData contract as monolithic:
    # short_summary and follow_up_questions come from the outline, not scraping.
    outline = ReportOutline(
        title="T",
        chapters=[Chapter(title="A", objective="o", source_ids=["S1"])],
        short_summary="Résumé exécutif produit par l'outline.",
        follow_up_questions=["Q1 ?", "Q2 ?"],
    )
    counter = {"outline": 0, "chapter": 0}
    fake = _make_fake_runner(outline, lambda title: f"Body {title} [S1].", counter)
    monkeypatch.setattr(outline_mod, "Runner", fake)
    monkeypatch.setattr("src.report_writer.chapters.Runner", fake)

    metrics: dict = {}
    report = await pipeline_mod.write_report_decomposed(
        "Q", "agenda", _sources(tmp_path), _research_info(tmp_path), metrics=metrics
    )

    assert report.short_summary == "Résumé exécutif produit par l'outline."
    assert report.follow_up_questions == ["Q1 ?", "Q2 ?"]
    # Honest cost: 1 outline call + 1 chapter call (no retry).
    assert metrics["llm_calls"] == 2


@pytest.mark.asyncio
async def test_pipeline_llm_calls_counts_retries(monkeypatch, tmp_path):
    outline = ReportOutline(
        title="T", chapters=[Chapter(title="A", objective="o", source_ids=["S1"])]
    )
    counter = {"outline": 0, "chapter": 0}
    # No [S#] -> guardrail retries once (chapter_max_revisions=1): 2 chapter calls.
    fake = _make_fake_runner(outline, lambda title: "Sans citation.", counter)
    monkeypatch.setattr(outline_mod, "Runner", fake)
    monkeypatch.setattr("src.report_writer.chapters.Runner", fake)
    monkeypatch.setattr(get_config().agents, "chapter_max_revisions", 1)

    metrics: dict = {}
    await pipeline_mod.write_report_decomposed(
        "Q", "agenda", _sources(tmp_path), _research_info(tmp_path), metrics=metrics
    )

    assert metrics["llm_calls"] == 3  # 1 outline + 2 chapter attempts


@pytest.mark.asyncio
async def test_pipeline_respects_chapter_budget_cap(monkeypatch, tmp_path):
    outline = ReportOutline(
        title="T",
        chapters=[
            Chapter(title="A", objective="o", source_ids=["S1"]),
            Chapter(title="B", objective="o", source_ids=["S2"]),
        ],
        short_summary="Résumé sous cap.",
        follow_up_questions=["Q1 ?"],
    )
    counter = {"outline": 0, "chapter": 0}
    fake = _make_fake_runner(outline, lambda title: f"Body {title} [S1].", counter)
    monkeypatch.setattr(outline_mod, "Runner", fake)
    monkeypatch.setattr("src.report_writer.chapters.Runner", fake)
    monkeypatch.setattr(get_config().agents, "writer_max_chapters", 1)

    report = await pipeline_mod.write_report_decomposed(
        "Q", "agenda", _sources(tmp_path), _research_info(tmp_path)
    )

    assert counter["chapter"] == 1  # capped
    assert "## A" in report.markdown_report
    assert "## B" not in report.markdown_report
    # The cap must not drop the outline's summary / follow-ups (regression guard).
    assert report.short_summary == "Résumé sous cap."
    assert report.follow_up_questions == ["Q1 ?"]


@pytest.mark.asyncio
async def test_pipeline_retries_chapter_without_citation(monkeypatch, tmp_path):
    outline = ReportOutline(
        title="T", chapters=[Chapter(title="A", objective="o", source_ids=["S1"])]
    )
    counter = {"outline": 0, "chapter": 0}
    # Never emits a [S#] citation -> guardrail should retry up to the budget.
    fake = _make_fake_runner(outline, lambda title: "Texte sans citation.", counter)
    monkeypatch.setattr(outline_mod, "Runner", fake)
    monkeypatch.setattr("src.report_writer.chapters.Runner", fake)
    monkeypatch.setattr(get_config().agents, "chapter_max_revisions", 1)

    report = await pipeline_mod.write_report_decomposed(
        "Q", "agenda", _sources(tmp_path), _research_info(tmp_path)
    )

    assert counter["chapter"] == 2  # initial attempt + 1 retry
    # Best-effort: the chapter is still kept, and Sources falls back to all sources.
    assert "## A" in report.markdown_report
    assert "- [S1] mips — mips.txt" in report.markdown_report
