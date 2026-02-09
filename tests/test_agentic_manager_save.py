from __future__ import annotations

import pytest

from src.agentic_manager import AgenticResearchManager
from src.agents.schemas import ReportData, ResearchInfo


class DummyServer:
    pass


@pytest.mark.asyncio
async def test_agentic_manager_saves_report(monkeypatch, tmp_path):
    report = ReportData(
        file_name="report.md",
        research_topic="Topic",
        short_summary="Short summary",
        markdown_report="# Report",
        follow_up_questions=["Q1"],
    )

    async def fake_agentic_research(self, _query, _research_info):
        return report

    save_calls: list[tuple] = []

    async def fake_save_final_report_function(
        output_dir, research_topic, markdown_report, short_summary, follow_up_questions
    ):
        save_calls.append(
            (output_dir, research_topic, markdown_report, short_summary, follow_up_questions)
        )
        return report

    monkeypatch.setattr(AgenticResearchManager, "_agentic_research", fake_agentic_research)
    monkeypatch.setattr(
        "src.agentic_manager.save_final_report_function",
        fake_save_final_report_function,
        raising=False,
    )
    monkeypatch.setattr("src.agentic_manager.create_file_planner_agent", lambda *_a, **_k: object())
    monkeypatch.setattr("src.agentic_manager.create_file_search_agent", lambda *_a, **_k: object())
    monkeypatch.setattr("src.agentic_manager.create_writer_agent", lambda *_a, **_k: object())
    monkeypatch.setattr(
        "src.agentic_manager.create_research_supervisor_agent", lambda *_a, **_k: object()
    )

    research_info = ResearchInfo(
        vector_store_name="store",
        vector_store_id=None,
        temp_dir=str(tmp_path),
        max_search_plan="1-2",
        output_dir=str(tmp_path / "out"),
    )

    manager = AgenticResearchManager()
    await manager.run(
        fs_server=DummyServer(),
        dataprep_server=DummyServer(),
        vector_mcp_server=None,
        query="<research_request>Q</research_request>",
        research_info=research_info,
    )

    assert save_calls == [(str(tmp_path / "out"), "Topic", "# Report", "Short summary", ["Q1"])]
