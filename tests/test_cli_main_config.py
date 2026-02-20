from __future__ import annotations

import importlib
import sys
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any

import pytest


@dataclass
class DummyBackend:
    store_id: str = "store-id"

    def resolve_store_id(self, _name: str, _config: Any) -> str:
        return self.store_id


class DummyAsyncCM:
    async def __aenter__(self):
        return self

    async def __aexit__(self, _exc_type, _exc, _tb):
        return False


class DummyManager:
    last_call: dict[str, Any] | None = None

    async def run(self, **kwargs: Any) -> None:
        DummyManager.last_call = kwargs


def _make_config(tmp_path) -> SimpleNamespace:
    return SimpleNamespace(
        logging=SimpleNamespace(
            level="INFO",
            silence_third_party=False,
            third_party_level="WARNING",
        ),
        manager=SimpleNamespace(default_manager="manager"),
        vector_store=SimpleNamespace(name="default-store", vector_store_id=None),
        agents=SimpleNamespace(max_search_plan="1-2", output_dir=str(tmp_path / "out")),
        debug=SimpleNamespace(enabled=False),
        mcp=SimpleNamespace(
            server_host="127.0.0.1",
            server_port=8001,
            http_timeout_seconds=5.0,
            client_timeout_seconds=60.0,
        ),
        vector_search=SimpleNamespace(provider="local"),
        vector_mcp=SimpleNamespace(
            tool_allowlist=[],
            command="echo",
            args=[],
            client_timeout_seconds=60.0,
        ),
    )


def _import_fresh_main():
    sys.modules.pop("src.main", None)
    return importlib.import_module("src.main")


def test_importing_main_does_not_initialize_config(monkeypatch):
    import src.config as config

    called = False
    original = config.get_config

    def spy(*args, **kwargs):
        nonlocal called
        called = True
        return original(*args, **kwargs)

    monkeypatch.setattr(config, "get_config", spy)
    _import_fresh_main()
    assert called is False


@pytest.mark.asyncio
async def test_cli_args_override_config_and_flow(monkeypatch, tmp_path):
    import src.run_research as run_research

    main = _import_fresh_main()
    config = _make_config(tmp_path)
    call_order: list[tuple[str, Any]] = []
    DummyManager.last_call = None

    def fake_get_config(config_path: str | None = None):
        call_order.append(("get_config", config_path))
        return config

    def fake_get_manager_class(manager_path: str):
        call_order.append(("get_manager_class", manager_path))
        return DummyManager

    syllabus_path = tmp_path / "syllabus.md"
    syllabus_path.write_text("Syllabus content", encoding="utf-8")

    monkeypatch.setattr(main, "get_config", fake_get_config)
    monkeypatch.setattr(main, "setup_run_logging", lambda **_kwargs: "test.log")
    monkeypatch.setattr(run_research, "get_config", fake_get_config)
    monkeypatch.setattr(run_research, "get_manager_class", fake_get_manager_class)
    monkeypatch.setattr(run_research, "setup_run_logging", lambda **_kwargs: "test.log")
    monkeypatch.setattr(run_research, "add_trace_processor", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(run_research, "MCPServerStdio", lambda **_kwargs: DummyAsyncCM())
    monkeypatch.setattr(run_research, "MCPServerSse", lambda **_kwargs: DummyAsyncCM())
    monkeypatch.setattr(run_research, "get_vector_backend", lambda _cfg: DummyBackend())
    monkeypatch.setattr(run_research.os.path, "exists", lambda _path: True)

    argv = [
        "agentic-research",
        "--config",
        "configs/tests/chroma_search/config-chroma-default.yaml",
        "--syllabus",
        str(syllabus_path),
        "--manager",
        "deep_manager",
        "--vector-store",
        "custom-store",
        "--dataprep-host",
        "dataprep.local",
        "--dataprep-port",
        "9999",
        "--max-search-plan",
        "5-7",
        "--output-dir",
        str(tmp_path / "custom-output"),
        "--debug",
    ]
    monkeypatch.setattr(sys, "argv", argv)

    await main.main()

    assert call_order[0] == ("get_config", argv[2])
    assert ("get_manager_class", "deep_manager") in call_order

    assert config.vector_store.name == "custom-store"
    assert config.agents.max_search_plan == "5-7"
    assert config.agents.output_dir == str(tmp_path / "custom-output")
    assert config.debug.enabled is True
    assert config.mcp.server_host == "dataprep.local"
    assert config.mcp.server_port == 9999

    assert DummyManager.last_call is not None
    assert DummyManager.last_call["query"].startswith("<research_request>\nSyllabus content")


@pytest.mark.asyncio
async def test_cli_query_from_input(monkeypatch, tmp_path):
    import src.run_research as run_research

    main = _import_fresh_main()
    config = _make_config(tmp_path)
    DummyManager.last_call = None

    monkeypatch.setattr(main, "get_config", lambda _path=None: config)
    monkeypatch.setattr(main, "setup_run_logging", lambda **_kwargs: "test.log")
    monkeypatch.setattr(run_research, "get_config", lambda _path=None: config)
    monkeypatch.setattr(run_research, "get_manager_class", lambda _path: DummyManager)
    monkeypatch.setattr(run_research, "setup_run_logging", lambda **_kwargs: "test.log")
    monkeypatch.setattr(run_research, "add_trace_processor", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(run_research, "MCPServerStdio", lambda **_kwargs: DummyAsyncCM())
    monkeypatch.setattr(run_research, "MCPServerSse", lambda **_kwargs: DummyAsyncCM())
    monkeypatch.setattr(run_research, "get_vector_backend", lambda _cfg: DummyBackend())
    monkeypatch.setattr(run_research.os.path, "exists", lambda _path: True)
    monkeypatch.setattr("builtins.input", lambda _prompt: "Interactive query")

    monkeypatch.setattr(sys, "argv", ["agentic-research"])

    await main.main()

    assert DummyManager.last_call is not None
    assert DummyManager.last_call["query"].startswith("<research_request>\nInteractive query")
