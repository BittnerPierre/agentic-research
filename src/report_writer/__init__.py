"""Decomposed report writer (spike — issue #196).

Splits the monolithic writer into smaller, parallelizable steps so large hybrid
models hosted on the Spark cluster stay fast and reliable:

- aggregate: programmatic source aggregation (no LLM, no MCP) run right after
  the search phase.

Further steps (chapter briefs, parallel drafting, assembly) land in follow-up
commits on the same branch.
"""

from .aggregate import aggregate_sources, extract_doc_ids, render_corpus, topic_from_filename

__all__ = [
    "aggregate_sources",
    "extract_doc_ids",
    "render_corpus",
    "topic_from_filename",
]
