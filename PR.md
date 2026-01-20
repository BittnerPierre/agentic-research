# PR: Vector backend factory, local mock + OpenAI compat, MCP port config

## Summary
- Introduce a provider-based vector backend factory in dataprep (local mock + OpenAI), restoring store-id abstraction and centralizing provider logic.
- Add tests for metadata download/store, late attachment flows, provider routing, and mocked OpenAI uploads.
- Add MCP server host/port config + CLI overrides and update client to use configured dataprep URL.
- Update prompts/specs and config defaults for vector search provider.

## Key Changes
- `src/dataprep/vector_backends.py`: backend interface + implementations; registry for store IDs.
- `src/dataprep/vector_search.py`: file-backed local search backend.
- `src/dataprep/vector_store_utils.py`: shared ingestion helpers.
- `src/dataprep/mcp_functions.py`: delegate upload/search to backend factory.
- `src/main.py`: dataprep URL uses config, provider setup moved to backend.
- `src/mcp/dataprep_server.py`: CLI flags for host/port/config.
- Tests: `tests/test_dataprep_late_attachment.py`, `tests/test_vector_search_openai_mock.py`, `tests/test_vector_search_providers.py`, `tests/test_config_vector_search_provider.py`, `tests/test_vector_search_flow.py`.

## Tests
- `poetry run pytest`
- `poetry run pytest tests/test_vector_search_openai_mock.py`
- `poetry run pytest tests/test_dataprep_late_attachment.py`

## Notes
- Local vector search is a mock/stand-in to validate workflow and late attachment sequencing.
- OpenAI flow is preserved for backward compatibility; provider selection is in config.
