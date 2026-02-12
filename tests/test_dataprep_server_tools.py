from __future__ import annotations

from types import SimpleNamespace

import pytest

import src.mcp.dataprep_server as dataprep_server


@pytest.mark.asyncio
async def test_download_and_store_url_tool_returns_filename(monkeypatch):
    monkeypatch.setattr(dataprep_server, "get_config", lambda: SimpleNamespace())
    monkeypatch.setattr(
        dataprep_server,
        "download_and_store_url",
        lambda url, _config: "downloaded.md",
    )

    server = dataprep_server.create_dataprep_server()
    tool = await server.get_tool("download_and_store_url_tool")
    result = await tool.run({"url": "https://example.com/doc"})

    assert result.content[0].text == "downloaded.md"


@pytest.mark.asyncio
async def test_download_and_store_url_tool_returns_error_string_on_failure(monkeypatch):
    monkeypatch.setattr(dataprep_server, "get_config", lambda: SimpleNamespace())

    def _raise_download_failure(_url, _config):
        raise ValueError("Unable to download content")

    monkeypatch.setattr(dataprep_server, "download_and_store_url", _raise_download_failure)

    server = dataprep_server.create_dataprep_server()
    tool = await server.get_tool("download_and_store_url_tool")
    result = await tool.run({"url": "https://arxiv.org/pdf/2306.02171.pdf"})

    assert result.content[0].text.startswith("ERROR: download_and_store_url failed for ")
    assert "Unable to download content" in result.content[0].text
