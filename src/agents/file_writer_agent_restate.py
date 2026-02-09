# Restate-enabled writer agent for POC evaluation.
from __future__ import annotations

from typing import Iterable

from pydantic import BaseModel
import restate
from restate.ext.openai import DurableRunner, durable_function_tool, restate_context

from agents.mcp import MCPServer

from .file_writer_agent import create_writer_agent
from .schemas import ReportData, ResearchInfo
from .utils import save_final_report_function


class WriterRestateRequest(BaseModel):
    prompt: str
    research_info: ResearchInfo


class SaveReportRequest(BaseModel):
    output_dir: str
    report: ReportData


@durable_function_tool
async def save_report_durable(request: SaveReportRequest) -> ReportData:
    return await restate_context().run_typed(
        "save_report",
        save_final_report_function,
        output_dir=request.output_dir,
        research_topic=request.report.research_topic,
        markdown_report=request.report.markdown_report,
        short_summary=request.report.short_summary,
        follow_up_questions=request.report.follow_up_questions,
    )


def build_writer_restate_service(
    mcp_servers: Iterable[MCPServer] | None = None,
    config_file: str | None = None,
) -> restate.Service:
    writer_agent = create_writer_agent(list(mcp_servers or []), config_file=config_file)
    writer_service = restate.Service("WriterAgentRestate")

    @writer_service.handler(name="run")
    async def run(_ctx: restate.Context, request: WriterRestateRequest) -> ReportData:
        result = await DurableRunner.run(
            writer_agent,
            request.prompt,
            context=request.research_info,
        )
        return result.final_output_as(ReportData)

    return writer_service


async def run_restate_writer_agent(
    prompt: str,
    research_info: ResearchInfo,
    mcp_servers: Iterable[MCPServer] | None = None,
    config_file: str | None = None,
) -> ReportData:
    writer_agent = create_writer_agent(list(mcp_servers or []), config_file=config_file)
    result = await DurableRunner.run(writer_agent, prompt, context=research_info)
    return result.final_output_as(ReportData)
