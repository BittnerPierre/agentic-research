"""Config parsing tests for vector_search.provider."""

from __future__ import annotations

from pathlib import Path

import yaml

from src.config import ConfigManager


def test_config_yaml_defaults_to_local_provider():
    config_path = Path(__file__).resolve().parents[1] / "config.yaml"
    config = ConfigManager(config_path).load_config()
    assert config.vector_search.provider == "local"


def test_config_manager_reads_provider_override(tmp_path):
    config_path = tmp_path / "config.yaml"
    config_data = {
        "config_name": "test",
        "vector_store": {"name": "vs", "description": "desc", "expires_after_days": 1},
        "vector_search": {"provider": "openai", "index_name": "idx"},
    }
    config_path.write_text(yaml.safe_dump(config_data), encoding="utf-8")

    config = ConfigManager(config_path).load_config()
    assert config.vector_search.provider == "openai"
