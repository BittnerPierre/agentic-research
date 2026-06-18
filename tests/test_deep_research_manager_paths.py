from pathlib import Path
from types import SimpleNamespace

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
async def test_file_search_returns_normalized_path_for_plain_string_output(
    monkeypatch, tmp_path: Path
):
    manager = _build_manager(tmp_path)
    manager.file_search_agent = object()

    summary_file = tmp_path / "mips_vs_rewoo.txt"
    summary_file.write_text("summary", encoding="utf-8")

    class _FakeResult:
        def __init__(self, output):
            self.final_output = output

    async def _fake_run(agent, input_text, context):
        del agent, input_text, context
        return _FakeResult("mips_vs_rewoo.txt")

    monkeypatch.setattr("src.deep_research_manager.Runner.run", _fake_run)
    monkeypatch.setattr(manager, "_record_usage", lambda *a, **k: None)

    result_path = await manager._file_search(
        FileSearchItem(query="mips rewoo", reason="comparison")
    )

    assert result_path == str(summary_file.resolve())
    assert manager.agent_calls["failures"] == 0


@pytest.mark.asyncio
async def test_file_search_returns_none_for_empty_output(monkeypatch, tmp_path: Path):
    manager = _build_manager(tmp_path)
    manager.file_search_agent = object()

    class _FakeResult:
        def __init__(self, output):
            self.final_output = output

    async def _fake_run(agent, input_text, context):
        del agent, input_text, context
        return _FakeResult("   ")

    monkeypatch.setattr("src.deep_research_manager.Runner.run", _fake_run)
    monkeypatch.setattr(manager, "_record_usage", lambda *a, **k: None)

    result_path = await manager._file_search(FileSearchItem(query="foo", reason="bar"))

    assert result_path is None
    assert manager.agent_calls["failures"] == 1


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


@pytest.mark.asyncio
async def test_run_fails_fast_before_writer_when_search_returns_no_usable_results(
    monkeypatch, tmp_path: Path
):
    manager = _build_manager(tmp_path)
    manager.research_info.vector_store_name = "vs"
    manager.research_info.vector_store_id = "vs_123"

    monkeypatch.setattr("src.deep_research_manager.create_knowledge_preparation_agent", lambda *_args: object())
    monkeypatch.setattr("src.deep_research_manager.create_file_planner_agent", lambda *_args: object())
    monkeypatch.setattr("src.deep_research_manager.create_file_search_agent", lambda *_args: object())
    monkeypatch.setattr("src.deep_research_manager.create_writer_agent", lambda *_args, **_kwargs: object())

    async def _prepare_knowledge(_query):
        return "agenda"

    async def _plan_file_searches(_agenda):
        return FileSearchPlan(
            searches=[FileSearchItem(query="q1", reason="r1", filenames=["2025.02v3.pdf"])]
        )

    async def _perform_file_searches(_plan):
        return []

    async def _write_report(_query, _search_results):
        raise AssertionError("writer should not run when retrieval returns no usable results")

    monkeypatch.setattr(manager, "_prepare_knowledge", _prepare_knowledge)
    monkeypatch.setattr(manager, "_plan_file_searches", _plan_file_searches)
    monkeypatch.setattr(manager, "_perform_file_searches", _perform_file_searches)
    monkeypatch.setattr(manager, "_write_report", _write_report)

    with pytest.raises(RuntimeError, match="No usable search results"):
        await manager.run(
            fs_server=SimpleNamespace(),
            dataprep_server=SimpleNamespace(),
            query="Analyse kb://2025.02v3.pdf",
            research_info=manager.research_info,
        )
