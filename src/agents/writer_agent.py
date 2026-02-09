# Agent used to synthesize a final report from the individual summaries.
from agents import Agent

from ..config import get_config
from .utils import get_writer_output_formatting, get_writer_output_type

def _build_prompt() -> str:
    config = get_config()
    output_format = config.agents.writer_output_format
    output_formatting = get_writer_output_formatting(output_format)

    return (
        "You are a senior researcher tasked with writing a cohesive report for a research query. "
        "You will be provided with the original query, and some initial research done by a research "
        "assistant.\n"
        "You should first come up with an outline for the report that describes the structure and "
        "flow of the report. Then, generate the report and return that as your final output.\n\n"
        "### OUTPUT FORMATING\n\n"
        f"{output_formatting}"
    )


_config = get_config()
writer_agent = Agent(
    name="WriterAgent",
    instructions=_build_prompt(),
    model="o3-mini",
    output_type=get_writer_output_type(_config.agents.writer_output_format),
)
