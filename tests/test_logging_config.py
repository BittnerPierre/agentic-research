"""Tests for logging configuration behavior."""

from __future__ import annotations

import logging

from src.logging_config import setup_run_logging


def test_setup_run_logging_sets_litellm_levels(tmp_path):
    log_dir = tmp_path / "logs"
    setup_run_logging(log_dir=str(log_dir), silence_third_party=True, third_party_level="ERROR")

    assert logging.getLogger("LiteLLM").level == logging.ERROR
    assert logging.getLogger("litellm").level == logging.ERROR

    logging.getLogger().handlers.clear()
