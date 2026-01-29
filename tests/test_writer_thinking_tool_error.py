import os

import pytest

from agents import Agent, Runner, function_tool
from agents.models import get_default_model_settings
from src.agents.file_writer_agent import dynamic_instructions
from src.agents.schemas import ReportData, ResearchInfo
from src.agents.utils import extract_model_name


def _has_live_mistral_config() -> bool:
    return bool(os.getenv("MISTRAL_API_KEY"))


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.skipif(
    os.getenv("RUN_INTEGRATION_TESTS") != "1",
    reason="Set RUN_INTEGRATION_TESTS=1 to run live integration tests.",
)
@pytest.mark.skipif(
    not _has_live_mistral_config(),
    reason="Set MISTRAL_API_KEY to run Mistral integration tests.",
)
async def test_writer_agent_includes_thinking_tag(tmp_path):
    """
    Integration test: uses a live model and expects a <thinking> block in the response text.
    """

    @function_tool
    async def read_multiple_files(paths: list[str]) -> str:
        parts = []
        for path in paths:
            with open(path, encoding="utf-8") as handle:
                parts.append(f"{path}:\n{handle.read()}")
        return "\n---\n".join(parts)

    files = [
        "prompt_engineering.txt",
        "advanced_retrieval.txt",
    ]
    for name in files:
        (tmp_path / name).write_text(f"Sample content for {name}.", encoding="utf-8")

    model = os.getenv("WRITER_MODEL_UNDER_TEST", "litellm/mistral/mistral-small-latest")
    model_settings = get_default_model_settings(extract_model_name(model))

    writer_agent = Agent(
        name="writer_agent",
        instructions=dynamic_instructions,
        model=model,
        output_type=ReportData,
        model_settings=model_settings,
        tools=[read_multiple_files],
    )

    context = ResearchInfo(
        temp_dir=str(tmp_path),
        output_dir=str(tmp_path),
        search_results=files,
    )

    result = await Runner.run(
        writer_agent,
        "Write the report from the files listed in the prompt.",
        context=context,
        max_turns=6,
    )

    final_output = result.final_output_as(ReportData, raise_if_incorrect_type=True)
    assert "## Raw Notes" in final_output.markdown_report
    assert "## Detailed Agenda" in final_output.markdown_report
    assert "## Report" in final_output.markdown_report
