from pathlib import Path

import pytest

from src.agents.schemas import FileSearchItem, FileSearchPlan, ResearchInfo
from src.deep_research_manager import DeepResearchManager


def _build_manager(tmp_path: Path) -> DeepResearchManager:
    manager = DeepResearchManager()
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    manager.research_info = ResearchInfo(
        temp_dir=str(tmp_path),
        output_dir=str(output_dir),
        search_results=[],
    )
    return manager


def test_normalize_search_result_path_accepts_existing_temp_file(tmp_path: Path):
    summary_file = tmp_path / "mips_summary.txt"
    summary_file.write_text("content", encoding="utf-8")
    manager = _build_manager(tmp_path)

    resolved = manager._normalize_search_result_path("mips_summary.txt")

    assert resolved == str(summary_file.resolve())


def test_normalize_search_result_path_rejects_absolute_outside_temp(tmp_path: Path):
    outside_file = tmp_path.parent / "doc__2205.11916__Large_Language_Models_are_Zero.md"
    outside_file.write_text("outside", encoding="utf-8")
    manager = _build_manager(tmp_path)

    resolved = manager._normalize_search_result_path(str(outside_file))

    assert resolved is None


def test_normalize_search_result_path_rejects_unknown_file(tmp_path: Path):
    manager = _build_manager(tmp_path)

    resolved = manager._normalize_search_result_path("missing_file.txt")

    assert resolved is None


def test_normalize_search_result_path_adds_txt_extension_when_missing(tmp_path: Path):
    summary_file = tmp_path / "rewoo_vs_mips.txt"
    summary_file.write_text("content", encoding="utf-8")
    manager = _build_manager(tmp_path)

    resolved = manager._normalize_search_result_path("rewoo_vs_mips")

    assert resolved == str(summary_file.resolve())


def test_normalize_search_result_path_handles_long_filenames(tmp_path: Path):
    manager = _build_manager(tmp_path)
    long_name = "System vs user prompts " * 40
    normalized = manager._normalize_search_filename(long_name)
    summary_file = tmp_path / f"{normalized}.txt"
    summary_file.write_text("content", encoding="utf-8")

    resolved = manager._normalize_search_result_path(long_name)

    assert resolved == str(summary_file.resolve())


@pytest.mark.asyncio
async def test_plan_file_searches_retries_once_on_invalid_json(monkeypatch, tmp_path: Path):
    manager = _build_manager(tmp_path)
    manager.file_planner_agent = object()

    calls = {"count": 0}

    class _FakeResult:
        def __init__(self, plan: FileSearchPlan):
            self._plan = plan

        def final_output_as(self, _schema):
            return self._plan

    async def _fake_run(agent, input_text, context):
        del agent, context
        calls["count"] += 1
        if calls["count"] == 1:
            raise ValueError("Invalid JSON when parsing")
        assert "IMPORTANT RETRY INSTRUCTION" in input_text
        return _FakeResult(
            FileSearchPlan(
                searches=[FileSearchItem(query="mips vs rewoo", reason="Need comparison details")]
            )
        )

    monkeypatch.setattr("src.deep_research_manager.Runner.run", _fake_run)

    plan = await manager._plan_file_searches("agenda")

    assert len(plan.searches) == 1
    assert calls["count"] == 2
    assert manager.agent_calls["file_planner_agent"] == 2
