"""Tests for mcp.client.stdio logging level."""

from __future__ import annotations

import logging

from src.logging_config import setup_run_logging


def test_setup_run_logging_sets_mcp_stdio_level(tmp_path):
    log_dir = tmp_path / "logs"
    setup_run_logging(log_dir=str(log_dir), silence_third_party=True, third_party_level="ERROR")

    assert logging.getLogger("mcp.client.stdio").level == logging.ERROR

    logging.getLogger().handlers.clear()
