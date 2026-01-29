"""Tests for Docker config defaults."""

from __future__ import annotations

from pathlib import Path

import yaml


def _load_config(path: str) -> dict:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


def test_docker_local_uses_direct_chroma_mcp_command():
    config = _load_config("configs/config-docker-local.yaml")
    assert config["vector_mcp"]["command"] == "chroma-mcp"


def test_docker_dgx_uses_direct_chroma_mcp_command():
    config = _load_config("configs/config-docker-dgx.yaml")
    assert config["vector_mcp"]["command"] == "chroma-mcp"
