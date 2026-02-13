"""Tests for QA agent prompt constraints."""

from __future__ import annotations

from types import SimpleNamespace

from src.agents.qa_agent import qa_instructions
from src.agents.schemas import ResearchInfo


def test_qa_instructions_use_vector_search_tool():
    context = SimpleNamespace(
        context=ResearchInfo(
            vector_store_name="agentic-research-local",
            vector_store_id="agentic-research-local",
            temp_dir="/tmp",
            max_search_plan="5-7",
            output_dir="output",
        )
    )

    instructions = qa_instructions(context, agent=None)

    assert "vector_search" in instructions
    assert "retrieved information" in instructions
