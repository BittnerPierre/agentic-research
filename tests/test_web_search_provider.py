"""Tests for the web_search.provider config and the You.com search tool."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from src.agents.search_agent import (
    _format_youcom_hits,
    _parse_youcom_response,
    create_search_agent,
)
from src.config import ConfigManager


def test_config_yaml_defaults_to_openai_web_search_provider():
    config_path = Path(__file__).resolve().parents[1] / "configs/config-default.yaml"
    config = ConfigManager(config_path).load_config()
    assert config.web_search.provider == "openai"


def test_config_manager_reads_youcom_web_search_provider(tmp_path):
    config_path = tmp_path / "configs/config-default.yaml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_data = {
        "config_name": "test",
        "vector_store": {"name": "vs", "description": "desc", "expires_after_days": 1},
        "web_search": {"provider": "youcom"},
    }
    config_path.write_text(yaml.safe_dump(config_data), encoding="utf-8")

    config = ConfigManager(config_path).load_config()
    assert config.web_search.provider == "youcom"


def test_create_search_agent_unknown_provider_raises():
    with pytest.raises(ValueError, match=r"web_search.provider"):
        create_search_agent("unknown")


def test_create_search_agent_youcom_exposes_youcom_tool():
    agent = create_search_agent("youcom")
    tool_names = [getattr(tool, "name", "") for tool in agent.tools]
    assert "youcom_search" in tool_names


def test_create_search_agent_openai_keeps_web_search_tool():
    agent = create_search_agent("openai")
    tool_names = [getattr(tool, "name", "") for tool in agent.tools]
    assert "youcom_search" not in tool_names


def test_parse_youcom_response_extracts_web_hits():
    inner = json.dumps({"results": {"web": [{"title": "t", "url": "u", "description": "d"}]}})
    message = {"jsonrpc": "2.0", "id": 1, "result": {"content": [{"type": "text", "text": inner}]}}
    body = "event: message\ndata: " + json.dumps(message) + "\n\n"
    assert _parse_youcom_response(body) == [{"title": "t", "url": "u", "description": "d"}]


def test_parse_youcom_response_supports_plain_json_body():
    inner = json.dumps({"results": {"web": [{"title": "t", "url": "u", "description": "d"}]}})
    message = {"jsonrpc": "2.0", "id": 1, "result": {"content": [{"type": "text", "text": inner}]}}
    body = json.dumps(message)
    assert _parse_youcom_response(body) == [{"title": "t", "url": "u", "description": "d"}]


def test_parse_youcom_response_raises_on_error():
    message = {"jsonrpc": "2.0", "id": 1, "result": {"isError": True, "content": []}}
    body = "data: " + json.dumps(message) + "\n\n"
    with pytest.raises(RuntimeError, match=r"You.com search"):
        _parse_youcom_response(body)


def test_format_youcom_hits_caps_and_formats():
    hits = [{"title": f"t{i}", "url": f"https://example.com/{i}", "description": f"d{i}"} for i in range(12)]
    out = _format_youcom_hits(hits)
    lines = [line for line in out.split("\n\n")]
    assert len(lines) == 10
    assert lines[0].startswith("1. t0\n")


def test_format_youcom_hits_empty():
    assert _format_youcom_hits([]) == "No results found."
