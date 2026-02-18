"""Tests for the agentic-research MCP server (Issue 83)."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from src.agents.schemas import ReportData
from src.mcp import agentic_research_server


@pytest.mark.asyncio
async def test_create_server_exposes_research_query_and_syllabus_tools():
    """Le serveur MCP expose les outils research_query et research_syllabus."""
    server = agentic_research_server.create_agentic_research_server()
    tools = await server.get_tools()
    assert "research_query" in tools
    assert "research_syllabus" in tools


@pytest.mark.asyncio
async def test_research_query_tool_returns_report_when_mock_succeeds(monkeypatch):
    """research_query retourne le rapport (short_summary, etc.) quand run_research_async réussit."""
    report = ReportData(
        file_name="report.md",
        research_topic="Test Topic",
        short_summary="Summary text",
        markdown_report="# Report\n\nContent",
        follow_up_questions=["Q1?"],
    )
    mock_run = AsyncMock(return_value=report)
    monkeypatch.setattr(
        agentic_research_server,
        "run_research_async",
        mock_run,
    )
    server = agentic_research_server.create_agentic_research_server()
    tool = await server.get_tool("research_query")
    result = await tool.run({"query": "Test query"})
    assert result.content[0].text is not None
    assert "Summary text" in result.content[0].text
    assert "Test Topic" in result.content[0].text
    mock_run.assert_called_once()
    # query can be positional or keyword
    call_args, call_kwargs = mock_run.call_args
    query_arg = call_kwargs.get("query") or (call_args[0] if call_args else None)
    assert query_arg == "<research_request>\nTest query\n</research_request>"


@pytest.mark.asyncio
async def test_research_syllabus_tool_wraps_content_and_calls_run(monkeypatch):
    """research_syllabus enveloppe le contenu dans research_request et appelle run_research_async."""
    report = ReportData(
        file_name="syllabus_report.md",
        research_topic="Syllabus Topic",
        short_summary="Syllabus summary",
        markdown_report="# Report",
        follow_up_questions=[],
    )
    mock_run = AsyncMock(return_value=report)
    monkeypatch.setattr(
        agentic_research_server,
        "run_research_async",
        mock_run,
    )
    server = agentic_research_server.create_agentic_research_server()
    tool = await server.get_tool("research_syllabus")
    result = await tool.run({"syllabus_content": "Chapter 1: Intro\nChapter 2: Deep dive"})
    assert "Syllabus summary" in result.content[0].text
    mock_run.assert_called_once()
    call_args, call_kwargs = mock_run.call_args
    query_arg = call_kwargs.get("query") or (call_args[0] if call_args else None)
    assert query_arg is not None
    assert "research_request" in query_arg
    assert "Chapter 1: Intro" in query_arg


@pytest.mark.asyncio
async def test_sync_call_returns_response_with_short_summary(monkeypatch):
    """Appel synchrone à research_query retourne une réponse contenant short_summary (contrat UAT)."""
    report = ReportData(
        file_name="report.md",
        research_topic="RAG",
        short_summary="Résumé court pour UAT",
        markdown_report="# Rapport",
        follow_up_questions=[],
    )
    monkeypatch.setattr(
        agentic_research_server,
        "run_research_async",
        AsyncMock(return_value=report),
    )
    server = agentic_research_server.create_agentic_research_server()
    tool = await server.get_tool("research_query")
    result = await tool.run({"query": "RAG en une phrase"})
    text = result.content[0].text or ""
    assert "short_summary" in text
    assert "Résumé court pour UAT" in text


@pytest.mark.asyncio
async def test_research_query_tool_returns_error_message_on_failure(monkeypatch):
    """research_query retourne un message d'erreur explicite en cas d'échec."""
    monkeypatch.setattr(
        agentic_research_server,
        "run_research_async",
        AsyncMock(side_effect=RuntimeError("Vector store unavailable")),
    )
    server = agentic_research_server.create_agentic_research_server()
    tool = await server.get_tool("research_query")
    result = await tool.run({"query": "Fail me"})
    assert result.content[0].text is not None
    assert "ERROR" in result.content[0].text
    assert "Vector store unavailable" in result.content[0].text
