"""Programmatic gate checks for the research workflow.

These gates enforce hard invariants that must hold before
the workflow can proceed to the next phase.
"""

from __future__ import annotations


class NoSearchResultsError(ValueError):
    """Raised when the research phase produced no exploitable results."""


def check_search_results_gate(search_results: list[str | None]) -> None:
    """Block report generation if no exploitable search result was produced.

    Args:
        search_results: List of file paths from the search phase.
            May contain None entries for failed individual searches.

    Raises:
        NoSearchResultsError: If no valid (non-None) result exists.
    """
    valid = [r for r in search_results if r is not None]
    if not valid:
        raise NoSearchResultsError(
            "No exploitable search results were produced. "
            "Cannot generate a report without sources. "
            "The run is marked as incomplete."
        )
