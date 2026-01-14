"""
Full Workflow Evaluator - End-to-End Research Workflow Evaluation

Extends the pattern from write_agent_eval.py to evaluate the complete research
workflow: supervisor → research → writer.

Validates:
1. Trajectory correctness (all agents executed in order)
2. Output quality (LLM-as-a-judge)
3. Coverage (topics addressed)

Manager-agnostic: Works with AgenticManager, DeepManager, etc.
"""

import asyncio
import os
import time
from pathlib import Path
from typing import Optional

from agents import Agent, Runner, TResponseInputItem, gen_trace_id, trace
from agents.mcp import MCPServer
from rich.console import Console

from src.agents.agentic_research_agent import create_research_supervisor_agent
from src.agents.file_search_agent import create_file_search_agent
from src.agents.file_search_planning_agent import create_file_planner_agent
from src.agents.file_writer_agent import create_writer_agent
from src.agents.schemas import ReportData, ResearchInfo
from src.config import get_config
from src.printer import Printer

from .eval_utils import (
    format_trajectory_report,
    save_result_input_list_to_json,
    save_trajectory_evaluation_report,
    validate_trajectory_spec,
)
from .prompts import llm_as_judge_prompt_V1
from .schemas import EvaluationResult
from .trajectory_specs import FULL_WORKFLOW_TRAJECTORY_SPEC


class FullWorkflowEvaluator:
    """
    Evaluates complete research workflow: supervisor → research → writer.

    Follows the pattern from write_agent_eval.py but extends to full workflow.
    """

    def __init__(self, output_dir: str = "evaluations/full_workflow_results"):
        self.console = Console()
        self.printer = Printer(self.console)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._config = get_config()

    async def run(
        self,
        fs_server: MCPServer,
        dataprep_server: MCPServer,
        research_info: ResearchInfo,
        syllabus: str,
    ) -> dict:
        """
        Run full workflow evaluation.

        Args:
            fs_server: Filesystem MCP server
            dataprep_server: Data preparation MCP server
            research_info: Research context with vector store ID
            syllabus: Research query/syllabus

        Returns:
            Evaluation results dictionary with trajectory and quality scores
        """
        self.fs_server = fs_server
        self.dataprep_server = dataprep_server
        self.research_info = research_info

        trace_id = gen_trace_id()
        with trace(
            "Full Workflow Evaluation",
            trace_id=trace_id,
            metadata={"evaluation_type": "full_workflow"},
        ):
            self.printer.update_item(
                "trace_id",
                f"View trace: https://platform.openai.com/traces/trace?trace_id={trace_id}",
                is_done=True,
                hide_checkmark=True,
            )

            self.printer.update_item(
                "starting",
                "Starting full workflow evaluation...",
                is_done=True,
                hide_checkmark=True,
            )

            # Execute full workflow
            report, messages = await self._run_full_workflow(syllabus)

            self.printer.update_item(
                "workflow_complete",
                f"Workflow complete: {report.file_name}",
                is_done=True,
            )

            # Evaluate trajectory
            trajectory_report, trajectory_file = await self._evaluate_trajectory(
                report, messages
            )

            self.printer.update_item(
                "trajectory_evaluated",
                f"Trajectory evaluated: {trajectory_file}",
                is_done=True,
            )

            # Evaluate quality
            quality_result = await self._evaluate_quality(report)

            self.printer.update_item(
                "quality_evaluated",
                f"Quality evaluated: {quality_result.judgment}",
                is_done=True,
            )

            self.printer.end()

            # Return evaluation results
            results = {
                "report_file": report.file_name,
                "report_summary": report.short_summary,
                "report_path": str(final_file_path),
                "trajectory_report": trajectory_report,
                "trajectory_file": trajectory_file,
                "quality_result": quality_result.model_dump(),
                "trace_id": trace_id,
            }

            print("\n=== EVALUATION RESULTS ===")
            print(f"Judgment: {quality_result.judgment}")
            print(f"Grades: {quality_result.grades}")
            print(f"Trajectory file: {trajectory_file}")

            return results

    async def _run_full_workflow(
        self, syllabus: str
    ) -> tuple[ReportData, list[TResponseInputItem]]:
        """
        Run the complete research workflow.

        This mimics AgenticResearchManager._agentic_research but also captures
        the messages for trajectory validation.

        Args:
            syllabus: Research query/syllabus

        Returns:
            Tuple of (report, messages)
        """
        self.printer.update_item("workflow", "Creating agents...")

        # Create all agents (same as AgenticResearchManager)
        file_planner_agent = create_file_planner_agent([self.fs_server])
        file_search_agent = create_file_search_agent(
            [self.fs_server], self.research_info.vector_store_id
        )
        writer_agent = create_writer_agent([self.fs_server])

        research_supervisor_agent = create_research_supervisor_agent(
            [self.dataprep_server],
            file_planner_agent,
            file_search_agent,
            writer_agent,
        )

        self.printer.update_item("workflow", "Running supervisor agent...")

        # Run supervisor (coordinates entire workflow)
        result = await Runner.run(
            research_supervisor_agent,
            syllabus,
            context=self.research_info,
            max_turns=25,
        )

        self.printer.update_item("workflow", "Extracting results...", is_done=True)

        # Extract results
        report = result.final_output_as(ReportData)
        messages = result.to_input_list()

        return report, messages

    async def _evaluate_trajectory(
        self, report: ReportData, messages: list[TResponseInputItem]
    ) -> tuple[str, str]:
        """
        Evaluate workflow trajectory.

        Validates that the workflow executed correctly:
        - Supervisor planned search
        - Supervisor executed search
        - Writer loaded data
        - Writer generated sections (Raw Notes, Agenda, Report)
        - Writer saved report

        Args:
            report: Generated report
            messages: Messages from workflow execution

        Returns:
            Tuple of (human_readable_report, report_file_path)
        """
        self.printer.update_item("trajectory", "Validating trajectory...")

        # Get model name for output files
        model_name = self._config.models.research_model
        safe_model_name = model_name.replace("/", "-")

        # Save report
        report_file_name = report.file_name
        base_file_name = os.path.basename(report_file_name).rsplit(".md", 1)[0]
        final_file_name = f"{base_file_name}_{safe_model_name}.md"
        final_file_path = self.output_dir / final_file_name

        with open(final_file_path, "w", encoding="utf-8") as f:
            f.write(report.markdown_report)

        print(f"📝 Report saved: {final_file_path}")

        # Save messages for debugging
        save_result_input_list_to_json(
            model_name=model_name,
            report_file_name=base_file_name + ".md",
            messages=messages,
            output_report_dir=str(self.output_dir),
        )

        # Validate trajectory
        spec = FULL_WORKFLOW_TRAJECTORY_SPEC["trajectory_spec"]
        validation_report = validate_trajectory_spec(messages, spec)

        # Format human-readable report
        human_readable_report = format_trajectory_report(
            model_name=model_name,
            evaluation=validation_report,
            title="Full Workflow Trajectory",
        )

        # Save trajectory report
        evaluation_report_file = save_trajectory_evaluation_report(
            model_name=model_name,
            output_report_dir=str(self.output_dir),
            report_file_name=base_file_name + ".md",
            human_readable_report=human_readable_report,
        )

        self.printer.update_item(
            "trajectory", "Trajectory validated", is_done=True
        )

        return human_readable_report, evaluation_report_file

    async def _evaluate_quality(self, report: ReportData) -> EvaluationResult:
        """
        Evaluate report quality using LLM-as-a-judge.

        Validates:
        - Format correctness (sections present)
        - Grounding in Raw Notes
        - Agenda adherence
        - Output usability

        Args:
            report: Generated report

        Returns:
            EvaluationResult with judgment and grades
        """
        self.printer.update_item("quality", "Evaluating report quality...")

        report_quality_agent = Agent(
            name="report_quality_agent",
            instructions=llm_as_judge_prompt_V1,
            model="openai/gpt-4.1-mini",
            output_type=EvaluationResult,
        )

        result = await Runner.run(
            report_quality_agent,
            report.markdown_report,
        )

        self.printer.update_item("quality", "Quality evaluated", is_done=True)

        return result.final_output_as(EvaluationResult)


async def main():
    """
    CLI entry point for full workflow evaluation.

    Usage:
        poetry run python evaluations/full_workflow_evaluator.py --syllabus "Python basics"
    """
    import argparse
    import tempfile

    from agents.mcp import MCPServerStdio, MCPServerSse

    parser = argparse.ArgumentParser(description="Evaluate full research workflow")
    parser.add_argument(
        "--syllabus",
        type=str,
        required=True,
        help="Research syllabus/query",
    )
    parser.add_argument(
        "--vector-store-name",
        type=str,
        required=True,
        help="Storage name to lookup/create (e.g., 'agentic_research_data')",
    )
    parser.add_argument(
        "--vector-store-id",
        type=str,
        help="Storage ID (optional override - for testing with specific data)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="evaluations/full_workflow_results",
        help="Output directory for results",
    )

    args = parser.parse_args()

    # Get or create vector store by name
    vector_store_id = args.vector_store_id
    if vector_store_id is None:
        from openai import OpenAI
        client = OpenAI()

        print(f"🔍 Looking up storage: '{args.vector_store_name}'")

        # Lookup vector store by name (inline to avoid cross-module imports)
        vector_stores = client.vector_stores.list()
        for vs in vector_stores:
            if vs.name == args.vector_store_name:
                vector_store_id = vs.id
                break

        if vector_store_id is None:
            print(f"📦 Creating new storage: '{args.vector_store_name}'")
            vector_store_obj = client.vector_stores.create(name=args.vector_store_name)
            vector_store_id = vector_store_obj.id
            print(f"✅ Storage created: {vector_store_id}")
        else:
            print(f"✅ Found existing storage: {vector_store_id}")
    else:
        print(f"✅ Using provided storage ID: {vector_store_id}")

    # Create temp/output directories
    temp_dir = tempfile.mkdtemp(prefix="eval_")
    output_dir = tempfile.mkdtemp(prefix="eval_output_")

    # Create ResearchInfo
    research_info = ResearchInfo(
        vector_store_id=vector_store_id,
        temp_dir=temp_dir,
        output_dir=output_dir,
    )

    # Create MCP servers
    fs_server = MCPServerStdio(
        name="FS_MCP_SERVER",
        params={
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-filesystem", temp_dir, output_dir],
        },
    )

    dataprep_server = MCPServerSse(
        name="DATAPREP_MCP_SERVER",
        params={
            "url": "http://localhost:8001/sse",
            "timeout": 60,
        },
        client_session_timeout_seconds=120,
    )

    async with fs_server, dataprep_server:
        evaluator = FullWorkflowEvaluator(output_dir=args.output_dir)

        results = await evaluator.run(
            fs_server=fs_server,
            dataprep_server=dataprep_server,
            research_info=research_info,
            syllabus=args.syllabus,
        )

        print("\n=== FINAL RESULTS ===")
        print(f"Report: {results['report_file']}")
        print(f"Judgment: {results['quality_result']['judgment']}")
        print(f"Trajectory: {results['trajectory_file']}")


def cli_main():
    """
    Synchronous CLI entry point (for poetry scripts).
    """
    asyncio.run(main())


if __name__ == "__main__":
    cli_main()
