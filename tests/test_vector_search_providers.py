"""Tests for vector search provider routing and tool selection."""

from __future__ import annotations

import pytest

from src.config import get_config
from src.dataprep.mcp_functions import upload_files_to_vectorstore
from src.dataprep.models import UploadResult
from src.dataprep.vector_backends import get_vector_backend


def _snapshot_config(config):
    return config.vector_search.model_copy(deep=True)


def _restore_config(config, snapshot):
    config.vector_search = snapshot


def test_vector_backend_factory_local():
    config = get_config()
    snapshot = _snapshot_config(config)
    config.vector_search.provider = "local"

    backend = get_vector_backend(config)
    assert backend.provider == "local"

    _restore_config(config, snapshot)


def test_vector_backend_factory_openai():
    config = get_config()
    snapshot = _snapshot_config(config)
    config.vector_search.provider = "openai"

    backend = get_vector_backend(config)
    assert backend.provider == "openai"

    _restore_config(config, snapshot)


def test_vector_backend_factory_chroma():
    config = get_config()
    snapshot = _snapshot_config(config)
    config.vector_search.provider = "chroma"

    backend = get_vector_backend(config)
    assert backend.provider == "chroma"

    _restore_config(config, snapshot)


def test_vector_backend_factory_unknown_provider():
    config = get_config()
    snapshot = _snapshot_config(config)
    config.vector_search.provider = "invalid"

    with pytest.raises(ValueError, match="Unknown vector_search.provider"):
        get_vector_backend(config)

    _restore_config(config, snapshot)


def test_file_search_agent_tool_selection():
    config = get_config()
    snapshot = _snapshot_config(config)

    from src.agents.file_search_agent import create_file_search_agent

    config.vector_search.provider = "openai"
    agent = create_file_search_agent(vector_store_id="vs_openai")
    assert agent.tools[0].__class__.__name__ == "FileSearchTool"

    config.vector_search.provider = "local"
    agent = create_file_search_agent()
    assert agent.tools[0].name == "vector_search"

    config.vector_search.provider = "chroma"
    agent = create_file_search_agent()
    assert agent.tools[0].name == "vector_search"

    _restore_config(config, snapshot)


def test_file_search_agent_chroma_instructions_do_not_reference_raw_chroma_tool():
    config = get_config()
    snapshot = _snapshot_config(config)
    config.vector_search.provider = "chroma"

    from src.agents.file_search_agent import dynamic_instructions

    class _Ctx:
        vector_store_name = "agentic-research-dgx"
        temp_dir = "/tmp/bench"

    class _Wrapper:
        context = _Ctx()

    instructions = dynamic_instructions(_Wrapper(), None)
    assert "chroma_query_documents" not in instructions

    _restore_config(config, snapshot)


def test_vector_search_default_provider_is_openai():
    config = get_config()
    snapshot = _snapshot_config(config)
    assert config.vector_search.provider == "openai"
    _restore_config(config, snapshot)


def test_upload_files_to_vectorstore_delegates_to_backend(monkeypatch):
    config = get_config()
    snapshot = _snapshot_config(config)
    config.vector_search.provider = "local"

    sentinel = UploadResult(
        vectorstore_id="stub",
        files_uploaded=[],
        files_attached=[],
        total_files_requested=0,
        upload_count=0,
        reuse_count=0,
        attach_success_count=0,
        attach_failure_count=0,
    )

    class _StubBackend:
        provider = "local"

        def upload_files(self, inputs, config, vectorstore_name):
            return sentinel

    monkeypatch.setattr(
        "src.dataprep.mcp_functions.get_vector_backend", lambda _cfg: _StubBackend()
    )

    result = upload_files_to_vectorstore(inputs=[], config=config, vectorstore_name="vs")
    assert result is sentinel

    _restore_config(config, snapshot)
