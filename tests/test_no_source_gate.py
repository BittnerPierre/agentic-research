"""Tests for the no-source gate: no report should be produced without search results."""

from __future__ import annotations

import os

import pytest

from src.gates import NoSearchResultsError, check_search_results_gate


class TestNoSourceGateNoPaths:
    """Gate must raise when search results list is empty or all None."""

    def test_empty_list_raises(self):
        with pytest.raises(NoSearchResultsError):
            check_search_results_gate([])

    def test_all_none_raises(self):
        with pytest.raises(NoSearchResultsError):
            check_search_results_gate([None, None, None])

    def test_error_message_is_descriptive(self):
        with pytest.raises(NoSearchResultsError, match=r"No exploitable search results"):
            check_search_results_gate([])

    def test_error_is_value_error_subclass(self):
        """Ensure callers catching ValueError also catch this."""
        with pytest.raises(ValueError):
            check_search_results_gate([])


class TestNoSourceGateFileContent:
    """Gate must raise when files exist but contain no meaningful content."""

    def _write_file(self, tmp: str, name: str, content: str) -> str:
        path = os.path.join(tmp, name)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return path

    def test_valid_file_passes(self, tmp_path):
        path = self._write_file(str(tmp_path), "result.txt", "A" * 200)
        check_search_results_gate([path])

    def test_mixed_with_some_none_and_valid_file_passes(self, tmp_path):
        path = self._write_file(str(tmp_path), "result.txt", "A" * 200)
        check_search_results_gate([None, path, None])

    def test_empty_files_raise(self, tmp_path):
        path = self._write_file(str(tmp_path), "empty.txt", "")
        with pytest.raises(NoSearchResultsError, match=r"none contain exploitable content"):
            check_search_results_gate([path])

    def test_trivially_small_files_raise(self, tmp_path):
        """Files with <50 bytes are considered trivial (e.g. just a header)."""
        path = self._write_file(str(tmp_path), "tiny.txt", "short")
        with pytest.raises(NoSearchResultsError):
            check_search_results_gate([path])

    def test_multiple_empty_files_raise(self, tmp_path):
        paths = [
            self._write_file(str(tmp_path), f"empty_{i}.txt", "")
            for i in range(3)
        ]
        with pytest.raises(NoSearchResultsError, match=r"3 file\(s\)"):
            check_search_results_gate(paths)

    def test_one_valid_among_empty_passes(self, tmp_path):
        """At least one file with real content is enough."""
        empty = self._write_file(str(tmp_path), "empty.txt", "")
        valid = self._write_file(str(tmp_path), "good.txt", "X" * 100)
        check_search_results_gate([empty, valid])

    def test_nonexistent_files_treated_as_empty(self, tmp_path):
        fake_path = os.path.join(str(tmp_path), "does_not_exist.txt")
        with pytest.raises(NoSearchResultsError):
            check_search_results_gate([fake_path])

    def test_mix_nonexistent_and_valid_passes(self, tmp_path):
        fake = os.path.join(str(tmp_path), "nope.txt")
        valid = self._write_file(str(tmp_path), "good.txt", "Y" * 100)
        check_search_results_gate([fake, valid])

    def test_boundary_exactly_threshold_raises(self, tmp_path):
        """File with exactly 50 bytes should NOT pass (must be strictly greater)."""
        path = self._write_file(str(tmp_path), "boundary.txt", "Z" * 50)
        with pytest.raises(NoSearchResultsError):
            check_search_results_gate([path])

    def test_boundary_above_threshold_passes(self, tmp_path):
        """File with 51 bytes should pass."""
        path = self._write_file(str(tmp_path), "ok.txt", "Z" * 51)
        check_search_results_gate([path])
