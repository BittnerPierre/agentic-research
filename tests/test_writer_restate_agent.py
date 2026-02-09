import pytest

from src.agents.file_writer_agent_restate import run_restate_writer_agent
from src.agents.schemas import ReportData, ResearchInfo


@pytest.mark.asyncio
async def test_run_restate_writer_agent_calls_durable_runner(monkeypatch):
    report = ReportData(
        file_name="report.md",
        research_topic="test_topic",
        short_summary="summary",
        markdown_report="# Report",
        follow_up_questions=["q1"],
    )

    class DummyResult:
        def final_output_as(self, _model):
            return report

    async def fake_run(agent, prompt, context=None):
        fake_run.calls.append({"agent": agent, "prompt": prompt, "context": context})
        return DummyResult()

    fake_run.calls = []

    monkeypatch.setattr(
        "src.agents.file_writer_agent_restate.DurableRunner.run",
        fake_run,
    )

    research_info = ResearchInfo(
        temp_dir="/tmp",
        output_dir="/tmp/output",
        search_results=["file1.txt"],
    )

    result = await run_restate_writer_agent("Test prompt", research_info, mcp_servers=[])

    assert result == report
    assert len(fake_run.calls) == 1
    assert fake_run.calls[0]["prompt"] == "Test prompt"
    assert fake_run.calls[0]["context"] == research_info
