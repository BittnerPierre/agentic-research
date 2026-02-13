from __future__ import annotations

from types import SimpleNamespace

from src.agents.knowledge_preparation_agent import dynamic_instructions
from src.agents.schemas import ResearchInfo


def test_dynamic_instructions_enforce_runtime_vector_store_name():
    context = SimpleNamespace(
        context=ResearchInfo(
            vector_store_name="agentic-research-dgx",
            vector_store_id=None,
            temp_dir="/tmp",
            output_dir="output",
        )
    )

    instructions = dynamic_instructions(context, agent=None)

    assert "fetch_vector_store_name" in instructions
    assert "upload_files_to_vectorstore_tool" in instructions
    assert "N'inventez jamais un nom de vector store" in instructions
    assert "agentic-research-dgx" in instructions
