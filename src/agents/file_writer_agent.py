# Agent used to synthesize a final report from the individual summaries.
from typing import Any, ClassVar

from pydantic import BaseModel

from agents import Agent, RunContextWrapper
from agents.extensions.handoff_prompt import RECOMMENDED_PROMPT_PREFIX
from agents.mcp import MCPServer
from agents.models import get_default_model_settings

from ..config import get_config
from .schemas import ReportData, ResearchInfo
from .utils import (
    adjust_model_settings_for_base_url,
    extract_model_name,
    load_prompt_from_file,
    resolve_model,
)

prompt_file = "write_prompt.md"


def dynamic_instructions(
    context: RunContextWrapper[ResearchInfo], agent: Agent[ResearchInfo]
) -> str:
    prompt_template = load_prompt_from_file("prompts", prompt_file)

    if prompt_template is None:
        raise ValueError(f"{prompt_file} is None")

    dynamic_prompt = prompt_template.format(RECOMMENDED_PROMPT_PREFIX=RECOMMENDED_PROMPT_PREFIX)

    prompt = (
        f"{dynamic_prompt}"
        f"The absolute path to **temporary filesystem** is `{context.context.temp_dir}`. "
        " You MUST use it ONLY to READ temporary data.\n\n"
    )
    search_results = context.context.search_results
    if search_results:
        prompt += "The search results are: - " + "\n - ".join(search_results)
    return prompt


class WriterDirective(BaseModel):
    # research_topic: str
    # """Main research topic."""

    # attention_points: Optional[str] = None
    # """Specific attention points to address (optional)."""

    # agenda_items: List[str]
    # """List of agenda items or report sections to cover."""

    search_results: list[str]
    """List of filenames resulting from research (e.g., .txt, .md, .pdf files)."""

    class Config:
        json_schema_extra: ClassVar[dict[str, Any]] = {
            "example": {
                "search_results": [
                    "impact_ai_education.pdf",
                    "bias_and_accessibility.txt",
                    "case_study_universities.md",
                ]
            }
        }
        # json_schema_extra = {
        #     "example": {
        #         "research_topic": "The impact of generative AI on higher education",
        #         "attention_points": "Ethics, accessibility, bias",
        #         "agenda_items": [
        #             "Introduction and context",
        #             "Analysis of pedagogical impacts",
        #             "Risks and opportunities",
        #             "Future perspectives"
        #         ],
        #         "search_results": [
        #             "impact_ai_education.pdf",
        #             "bias_and_accessibility.txt",
        #             "case_study_universities.md"
        #         ]
        #     }
        # }


def create_writer_agent(
    mcp_servers: list[MCPServer] | None = None,
    do_save_report: bool = True,
    config_file: str | None = None,
):
    mcp_servers = mcp_servers or []

    config = get_config(config_file)
    model_spec = config.models.writer_model
    model = resolve_model(model_spec)

    model_name = extract_model_name(model_spec)
    model_settings = get_default_model_settings(model_name)
    adjust_model_settings_for_base_url(model_spec, model_settings)

    writer_agent = Agent(
        name="writer_agent",
        instructions=dynamic_instructions,
        model=model,
        output_type=ReportData,
        mcp_servers=mcp_servers,
        # handoffs=[save_agent],
        # tools=[
        #         save_report,
        #     ],
        model_settings=model_settings,
    )

    return writer_agent
