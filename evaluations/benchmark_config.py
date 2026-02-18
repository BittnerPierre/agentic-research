"""Benchmark configuration helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


def default_benchmark_config_path() -> Path:
    return Path(__file__).resolve().parents[1] / "configs" / "benchmark-default.yaml"


@dataclass(slots=True)
class BenchmarkConfig:
    runs: int = 2
    output_dir: str = "benchmarks"
    syllabus_file: str = "test_files/query_advanced_1.md"
    config_file: str = "configs/config-docker-dgx.yaml"
    vector_store_name: str | None = None
    timeout_seconds: int | None = None
    report_warmup: bool = False
    drop_worst_run: bool = False
    keep_services: bool = False
    models: list[str] = field(default_factory=list)


def _as_bool(value: Any, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _as_int(value: Any, default: int | None) -> int | None:
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def load_benchmark_config(path: str | None = None) -> BenchmarkConfig:
    config_path = Path(path) if path else default_benchmark_config_path()
    if not config_path.exists():
        raise FileNotFoundError(f"Benchmark config not found: {config_path}")

    with open(config_path, encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    bench = raw.get("benchmark", raw)
    return BenchmarkConfig(
        runs=_as_int(bench.get("runs"), 2) or 2,
        output_dir=str(bench.get("output_dir") or "benchmarks"),
        syllabus_file=str(bench.get("syllabus_file") or "test_files/query_advanced_1.md"),
        config_file=str(bench.get("config_file") or "configs/config-docker-dgx.yaml"),
        vector_store_name=bench.get("vector_store_name"),
        timeout_seconds=_as_int(bench.get("timeout_seconds"), None),
        report_warmup=_as_bool(bench.get("report_warmup"), False),
        drop_worst_run=_as_bool(bench.get("drop_worst_run"), False),
        keep_services=_as_bool(bench.get("keep_services"), False),
        models=list(bench.get("models", [])) if bench.get("models") is not None else [],
    )
