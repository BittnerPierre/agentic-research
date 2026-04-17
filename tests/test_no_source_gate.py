"""Tests for the no-source gate: no report should be produced without search results."""

from __future__ import annotations

import pytest

from src.agents.schemas import ResearchInfo
from src.gates import NoSearchResultsError, check_search_results_gate


class TestNoSourceGate:
    """Gate function must raise when search results are empty or all None."""

    def _make_research_info(self) -> ResearchInfo:
        return ResearchInfo(
            vector_store_id="vs_test",
            temp_dir="/tmp/test",
            max_search_plan="3-5",
            output_dir="output/",
        )

    def test_empty_list_raises(self):
        with pytest.raises(NoSearchResultsError):
            check_search_results_gate([])

    def test_all_none_raises(self):
        with pytest.raises(NoSearchResultsError):
            check_search_results_gate([None, None, None])

    def test_valid_results_pass(self):
        # Should not raise
        check_search_results_gate(["/tmp/test/result1.txt", "/tmp/test/result2.txt"])

    def test_mixed_with_some_none_passes(self):
        # Some None results are acceptable as long as at least one is valid
        check_search_results_gate([None, "/tmp/test/result1.txt", None])

    def test_single_valid_result_passes(self):
        check_search_results_gate(["/tmp/test/result.txt"])

    def test_error_message_is_descriptive(self):
        with pytest.raises(NoSearchResultsError, match=r"No exploitable search results"):
            check_search_results_gate([])

    def test_error_is_value_error_subclass(self):
        """Ensure callers catching ValueError also catch this."""
        with pytest.raises(ValueError):
            check_search_results_gate([])
