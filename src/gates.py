"""Programmatic gate checks for the research workflow.

These gates enforce hard invariants that must hold before
the workflow can proceed to the next phase.
"""

from __future__ import annotations

import os

# Minimum content size in bytes to consider a search result file exploitable.
# Files at or below this threshold are treated as empty/trivial.
_MIN_CONTENT_BYTES = 50


class NoSearchResultsError(ValueError):
    """Raised when the research phase produced no exploitable results."""


def check_search_results_gate(search_results: list[str | None]) -> None:
    """Block report generation if no exploitable search result was produced.

    Checks two levels:
    1. At least one non-None file path must exist in the results.
    2. At least one of those files must exist on disk and contain
       meaningful content (more than a trivial number of bytes).

    Args:
        search_results: List of file paths from the search phase.
            May contain None entries for failed individual searches.

    Raises:
        NoSearchResultsError: If no valid, non-empty result exists.
    """
    valid_paths = [r for r in search_results if r is not None]
    if not valid_paths:
        raise NoSearchResultsError(
            "No exploitable search results were produced. "
            "Cannot generate a report without sources. "
            "The run is marked as incomplete."
        )

    exploitable = 0
    for path in valid_paths:
        try:
            size = os.path.getsize(path)
            if size > _MIN_CONTENT_BYTES:
                exploitable += 1
        except OSError:
            # File does not exist or is inaccessible — skip it.
            continue

    if exploitable == 0:
        raise NoSearchResultsError(
            f"Search produced {len(valid_paths)} file(s), but none contain "
            f"exploitable content (>{_MIN_CONTENT_BYTES} bytes). "
            "Cannot generate a report without substantive sources. "
            "The run is marked as incomplete."
        )
