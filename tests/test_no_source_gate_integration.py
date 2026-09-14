"""Integration test reproducing the run_2 bug: search agents return file paths
but the files contain no real content from vector_search.

The DeepResearchManager should raise NoSearchResultsError instead of
producing a false-positive report.

Bug observed in benchmarks/run_2 (2026-03-13):
- 4 file_search_agents ran, 0 failures reported
- 3 files written to temp_dir, but with empty/trivial content
- Writer produced a report saying "No files were attached for this query"
- LLM-as-judge gave PASS with all A grades
- context_relevance was 0.3 (no actual retrieved sources)
"""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.agents.schemas import FileSearchItem, FileSearchPlan, ResearchInfo
from src.deep_research_manager import DeepResearchManager
from src.gates import NoSearchResultsError


@pytest.fixture
def research_info(tmp_path):
    return ResearchInfo(
        vector_store_id="vs_test",
        temp_dir=str(tmp_path),
        max_search_plan="3-5",
        output_dir=str(tmp_path / "output"),
    )


@pytest.fixture
def search_plan():
    """A search plan similar to what run_2 produced."""
    return FileSearchPlan(
        searches=[
            FileSearchItem(query="prompt engineering techniques", reason="Module 1 coverage"),
            FileSearchItem(query="RAG retrieval augmented generation", reason="Module 2 coverage"),
            FileSearchItem(query="multi agent systems", reason="Module 3 coverage"),
            FileSearchItem(query="ChatGPT API integration", reason="Module 4 coverage"),
        ]
    )


def _create_empty_search_results(tmp_path, count=3):
    """Simulate what run_2 produced: files exist but contain no real content.

    In the actual bug, vector_search returned nothing useful, so the
    file_search_agent wrote files with trivial or no content.
    """
    results = []
    for i in range(count):
        path = os.path.join(str(tmp_path), f"search_result_{i}.txt")
        with open(path, "w", encoding="utf-8") as f:
            # Empty or trivially small — like the run_2 files
            f.write("")
        results.append(path)
    # One search returned None (failed silently)
    results.append(None)
    return results


def _create_valid_search_results(tmp_path, count=3):
    """Simulate a healthy run with real content in search result files."""
    results = []
    for i in range(count):
        path = os.path.join(str(tmp_path), f"search_result_{i}.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write(f"Search result {i}\n\n" + "Substantive research content. " * 20)
        results.append(path)
    return results


class TestRun2BugReproduction:
    """Reproduce the exact failure mode from benchmarks/run_2."""

    @pytest.mark.asyncio
    async def test_empty_search_files_block_writer(self, tmp_path, research_info, search_plan):
        """The core bug: search 'succeeds' but files are empty.

        The manager must raise NoSearchResultsError instead of calling _write_report.
        """
        manager = DeepResearchManager()
        empty_results = _create_empty_search_results(tmp_path)

        # Mock the phases that precede the gate:
        # - _prepare_knowledge returns an agenda string
        # - _plan_file_searches returns the search plan
        # - _perform_file_searches returns file paths (the bug: files exist but empty)
        # We do NOT mock _write_report — it must never be called
        with (
            patch.object(manager, "_prepare_knowledge", new_callable=AsyncMock, return_value="Test agenda"),
            patch.object(manager, "_plan_file_searches", new_callable=AsyncMock, return_value=search_plan),
            patch.object(manager, "_perform_file_searches", new_callable=AsyncMock, return_value=empty_results),
            patch.object(manager, "_write_report", new_callable=AsyncMock) as mock_write,
        ):
            fs_server = MagicMock()
            dataprep_server = MagicMock()

            with pytest.raises(NoSearchResultsError, match=r"none contain exploitable content"):
                await manager.run(fs_server, dataprep_server, "<research_request>test</research_request>", research_info)

            # The writer must NEVER have been called
            mock_write.assert_not_called()

    @pytest.mark.asyncio
    async def test_valid_search_files_proceed_to_writer(self, tmp_path, research_info, search_plan):
        """Control test: when files have real content, writer IS called."""
        manager = DeepResearchManager()
        valid_results = _create_valid_search_results(tmp_path)

        mock_report = MagicMock()
        mock_report.short_summary = "Test summary"
        mock_report.research_topic = "Test"
        mock_report.markdown_report = "# Test"
        mock_report.follow_up_questions = []
        mock_report.file_name = "test.md"

        with (
            patch.object(manager, "_prepare_knowledge", new_callable=AsyncMock, return_value="Test agenda"),
            patch.object(manager, "_plan_file_searches", new_callable=AsyncMock, return_value=search_plan),
            patch.object(manager, "_perform_file_searches", new_callable=AsyncMock, return_value=valid_results),
            patch.object(manager, "_write_report", new_callable=AsyncMock, return_value=mock_report) as mock_write,
            patch("src.deep_research_manager.save_final_report_function", new_callable=AsyncMock, return_value=mock_report),
        ):
            fs_server = MagicMock()
            dataprep_server = MagicMock()

            await manager.run(fs_server, dataprep_server, "<research_request>test</research_request>", research_info)

            # Writer MUST have been called exactly once
            mock_write.assert_called_once()
