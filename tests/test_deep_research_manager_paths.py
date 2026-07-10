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
async def test_file_search_returns_normalized_path_for_plain_string_output(
    monkeypatch, tmp_path: Path
):
    """file_search_agent has no output_type (dropped in commit 2f35b47) — its
    final_output is a plain string containing the filename. _file_search must
    accept that and resolve it to the absolute path. Previously the manager
    called result.final_output_as(FileSearchResult).file_name, which raises
    AttributeError on a str and the `except Exception` silently returned None,
    making search_results empty and the writer receive "Search results: None".
    """
    manager = _build_manager(tmp_path)
    manager.file_search_agent = object()

    # Simulate file written by the agent via its MCP write_file tool.
    summary_file = tmp_path / "mips_vs_rewoo.txt"
    summary_file.write_text("summary", encoding="utf-8")

    class _FakeResult:
        def __init__(self, output):
            self.final_output = output

        def final_output_as(self, cls):
            from typing import cast

            return cast(cls, self.final_output)

    async def _fake_run(agent, input_text, context):
        del agent, input_text, context
        # Agent obeys file_search_prompt.md ("return only the name of the file"):
        # final_output is a plain string, not a FileSearchResult.
        return _FakeResult("mips_vs_rewoo.txt")

    monkeypatch.setattr("src.deep_research_manager.Runner.run", _fake_run)
    monkeypatch.setattr(manager, "_record_usage", lambda *a, **k: None)

    result_path = await manager._file_search(
        FileSearchItem(query="mips rewoo", reason="comparison")
    )

    assert result_path == str(summary_file.resolve()), (
        f"Expected normalized temp path, got {result_path!r}"
    )
    assert manager.agent_calls["failures"] == 0


@pytest.mark.asyncio
async def test_file_search_returns_none_for_empty_output(monkeypatch, tmp_path: Path):
    """When the agent returns an empty / whitespace final_output, _file_search
    should mark a failure and return None (no silent fake-success)."""
    manager = _build_manager(tmp_path)
    manager.file_search_agent = object()

    class _FakeResult:
        def __init__(self, output):
            self.final_output = output

        def final_output_as(self, cls):
            from typing import cast

            return cast(cls, self.final_output)

    async def _fake_run(agent, input_text, context):
        del agent, input_text, context
        return _FakeResult("   ")

    monkeypatch.setattr("src.deep_research_manager.Runner.run", _fake_run)
    monkeypatch.setattr(manager, "_record_usage", lambda *a, **k: None)

    result_path = await manager._file_search(FileSearchItem(query="foo", reason="bar"))

    assert result_path is None
    assert manager.agent_calls["failures"] == 1


@pytest.mark.asyncio
async def test_file_search_retries_once_on_exception_then_succeeds(monkeypatch, tmp_path: Path):
    manager = _build_manager(tmp_path)
    manager.file_search_agent = object()
    summary_file = tmp_path / "mips.txt"
    summary_file.write_text("MIPS retrieves vectors [doc_mips:0].", encoding="utf-8")

    calls = {"count": 0}

    class _FakeResult:
        final_output = "mips.txt"

    async def _fake_run(agent, input_text, context):
        del agent, input_text, context
        calls["count"] += 1
        if calls["count"] == 1:
            raise TimeoutError("search timed out")
        return _FakeResult()

    monkeypatch.setattr("src.deep_research_manager.Runner.run", _fake_run)
    monkeypatch.setattr(manager, "_record_usage", lambda *a, **k: None)

    result = await manager._file_search(FileSearchItem(query="mips", reason="need summary"))

    assert result == str(summary_file.resolve())
    assert calls["count"] == 2
    assert manager.agent_calls["file_search_agent"] == 2
    assert manager.agent_calls["failures"] == 0
    assert manager.search_failure_breakdown == {}


@pytest.mark.asyncio
async def test_file_search_retries_when_first_result_has_no_chunk_citation(
    monkeypatch, tmp_path: Path
):
    manager = _build_manager(tmp_path)
    manager.file_search_agent = object()
    summary_file = tmp_path / "rewoo.txt"

    calls = {"count": 0}

    class _FakeResult:
        final_output = "rewoo.txt"

    async def _fake_run(agent, input_text, context):
        del agent, context
        calls["count"] += 1
        if calls["count"] == 1:
            summary_file.write_text("ReWOO plans without citations.", encoding="utf-8")
            assert "IMPORTANT RETRY INSTRUCTION" not in input_text
        else:
            summary_file.write_text(
                "ReWOO plans without observation [rewoo.txt:0].", encoding="utf-8"
            )
            assert "IMPORTANT RETRY INSTRUCTION" in input_text
        return _FakeResult()

    monkeypatch.setattr("src.deep_research_manager.Runner.run", _fake_run)
    monkeypatch.setattr(manager, "_record_usage", lambda *a, **k: None)

    result = await manager._file_search(FileSearchItem(query="rewoo", reason="need summary"))

    assert result == str(summary_file.resolve())
    assert calls["count"] == 2
    assert manager.agent_calls["file_search_agent"] == 2
    assert manager.agent_calls["failures"] == 0


@pytest.mark.asyncio
async def test_file_search_keeps_first_uncited_result_when_retry_then_raises(
    monkeypatch, tmp_path: Path
):
    manager = _build_manager(tmp_path)
    manager.file_search_agent = object()
    summary_file = tmp_path / "fallback.txt"

    calls = {"count": 0}

    class _FakeResult:
        final_output = "fallback.txt"

    async def _fake_run(agent, input_text, context):
        del agent, input_text, context
        calls["count"] += 1
        if calls["count"] == 1:
            summary_file.write_text("Fallback summary without citations.", encoding="utf-8")
            return _FakeResult()
        raise TimeoutError("retry timed out")

    monkeypatch.setattr("src.deep_research_manager.Runner.run", _fake_run)
    monkeypatch.setattr(manager, "_record_usage", lambda *a, **k: None)

    result = await manager._file_search(FileSearchItem(query="fallback", reason="need summary"))

    assert result == str(summary_file.resolve())
    assert calls["count"] == 2
    assert manager.agent_calls["file_search_agent"] == 2
    assert manager.agent_calls["failures"] == 0
    assert manager.search_failure_breakdown == {}


@pytest.mark.asyncio
async def test_file_search_records_terminal_exception_details(
    monkeypatch, tmp_path: Path, caplog: pytest.LogCaptureFixture
):
    manager = _build_manager(tmp_path)
    manager.file_search_agent = object()

    async def _fake_run(agent, input_text, context):
        del agent, input_text, context
        raise TimeoutError("still too slow")

    monkeypatch.setattr("src.deep_research_manager.Runner.run", _fake_run)

    with caplog.at_level("WARNING"):
        result = await manager._file_search(FileSearchItem(query="ann", reason="need summary"))

    assert result is None
    assert manager.agent_calls["file_search_agent"] == 2
    assert manager.agent_calls["failures"] == 1
    assert manager.search_failure_breakdown == {"exception:TimeoutError": 1}
    assert "still too slow" in caplog.text


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
