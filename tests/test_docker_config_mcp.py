"""Tests for Docker config defaults."""

from __future__ import annotations

from pathlib import Path

import yaml


def _load_config(path: str) -> dict:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


def test_docker_local_does_not_define_vector_mcp_for_chroma_provider():
    config = _load_config("configs/config-docker-local.yaml")
    assert config["vector_search"]["provider"] == "chroma"
    assert "vector_mcp" not in config


def test_docker_dgx_does_not_define_vector_mcp_for_chroma_provider():
    config = _load_config("configs/config-docker-dgx.yaml")
    assert config["vector_search"]["provider"] == "chroma"
    assert "vector_mcp" not in config
