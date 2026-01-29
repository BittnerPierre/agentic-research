"""Ensure Dockerfiles do not copy runtime data into images."""

from __future__ import annotations

from pathlib import Path


def _read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def test_backend_dockerfile_does_not_copy_data():
    contents = _read("docker/Dockerfile.backend")
    assert "COPY data" not in contents


def test_dataprep_dockerfile_does_not_copy_data():
    contents = _read("docker/Dockerfile.dataprep")
    assert "COPY data" not in contents
