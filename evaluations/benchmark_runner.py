"""
Benchmark Runner - Orchestrate model setup benchmarks

Runs complete benchmarks for model setups, capturing all metrics:
- Quality (LLM-as-a-judge)
- RAG Triad (Groundedness, Context/Answer Relevance)
- Timing (total + per phase)
- Agent calls (per agent + total + failures)
"""

import argparse
import asyncio
import json
import os
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path

from agentic_research.agents.schemas import ResearchInfo
from agentic_research.config import get_config
from agents import Agent, Runner
from agents.mcp import MCPServerSse, MCPServerStdio

from .benchmark_trace_processor import BenchmarkTraceProcessor
from .prompts import llm_as_judge_prompt_v1
from .rag_triad_evaluator import evaluate_rag_triad, extract_raw_notes_from_report
from .schemas import EvaluationResult
from .scoring import compute_score_breakdown
from .setup_detector import detect_active_setup, get_setup_summary
from .spec_compliance_evaluator import evaluate_spec_compliance
from .trace_analyzer import TraceAnalyzer


class BenchmarkRunner:
    """
    Orchestrates benchmarks for model setups.

    Runs complete evaluation workflow and captures all metrics.
    """

    def __init__(self, output_dir: str = "benchmarks"):
        """
        Initialize benchmark runner.

        Args:
            output_dir: Base directory for benchmark results
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _quality_tier_from_score(self, quality_score_100: float) -> str:
        """Map quality score to a user-facing tier."""
        if quality_score_100 >= 95.0:
            return "GOOD"
        if quality_score_100 >= 80.0:
            return "PASS"
        if quality_score_100 >= 60.0:
            return "BORDERLINE"
        return "FAIL"

    async def run_benchmark(
        self,
        config_file: str,
        syllabus_file: str,
        num_runs: int = 2,
        vector_store_name: str | None = None,
    ) -> dict:
        """
        Run complete benchmark for active setup.

        Args:
            config_file: Path to config YAML
            syllabus_file: Path to syllabus/query file
            num_runs: Number of runs (default: 2 for outlier detection)
            vector_store_name: Vector store name (required for Chroma)

        Returns:
            Complete benchmark results with all metrics
        """
        # 1. Detect active setup
        print("🔍 Detecting active setup...")
        setup_metadata = detect_active_setup()
        print(get_setup_summary(setup_metadata))

        # 2. Load syllabus
        syllabus = self._load_syllabus(syllabus_file)

        # 3. Create run directory
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        setup_name = setup_metadata["setup_name"]
        run_dir = self.output_dir / f"run_{timestamp}" / setup_name
        run_dir.mkdir(parents=True, exist_ok=True)

        print(f"\n📂 Results will be saved to: {run_dir}")

        # 4. Run N evaluations
        runs = []
        for i in range(num_runs):
            print(f"\n{'='*60}")
            print(f"📊 Run {i+1}/{num_runs}")
            print(f"{'='*60}")

            run_result = await self._run_single_evaluation(
                config_file=config_file,
                syllabus=syllabus,
                run_dir=run_dir / f"run_{i+1}",
                vector_store_name=vector_store_name,
            )
            runs.append(run_result)

            print(f"\n✅ Run {i+1} completed:")
            print(f"   - Timing: {run_result['timing']['total_seconds']:.1f}s")
            print(
                "   - Quality: "
                f"{self._quality_tier_from_score(run_result['scores']['content_quality_100'])}"
            )
            print(f"   - Agent calls: {run_result['agent_calls']['total']}")
            print(f"   - Overall score: {run_result['scores']['overall_100']:.1f}/100")
            print(f"   - Spec compliance: {run_result['scores']['spec_compliance_100']:.1f}/100")
            print(f"   - Content quality: {run_result['scores']['content_quality_100']:.1f}/100")
            print(f"   - RAG compliance: {run_result['scores']['rag_compliance_100']:.1f}/100")
            print(f"   - Efficiency: {run_result['scores']['efficiency_100']:.1f}/100")

        # 5. Detect outliers
        print("\n🔍 Analyzing runs...")
        outliers = self._detect_outliers(runs)
        if outliers:
            print(f"⚠️  Outliers detected: {outliers}")
        else:
            print("✅ No outliers detected")

        # 6. Compute averages
        average = self._compute_average(runs)

        # 7. Save complete benchmark result
        benchmark_result = {
            "setup_metadata": setup_metadata,
            "config_file": config_file,
            "syllabus_file": syllabus_file,
            "timestamp": timestamp,
            "commit_hash": self._get_commit_hash(),
            "num_runs": num_runs,
            "runs": runs,
            "average": average,
            "outliers": outliers,
        }

        result_file = run_dir.parent / "benchmark_result.json"
        with open(result_file, "w", encoding="utf-8") as f:
            json.dump(benchmark_result, f, indent=2)

        print(f"\n💾 Benchmark results saved: {result_file}")

        return benchmark_result

    async def _run_single_evaluation(
        self,
        config_file: str,
        syllabus: str,
        run_dir: Path,
        vector_store_name: str | None,
    ) -> dict:
        """
        Run a single evaluation with full metrics capture.

        Args:
            config_file: Config file path
            syllabus: Research query/syllabus
            run_dir: Directory for this run's results
            vector_store_name: Vector store name

        Returns:
            Complete evaluation results with all metrics
        """
        run_dir.mkdir(parents=True, exist_ok=True)

        config = get_config(config_file)

        # Create temp directories
        temp_dir = tempfile.mkdtemp(prefix="bench_")
        output_dir = str(run_dir)
        temp_dir, output_dir = self._normalize_runtime_paths(temp_dir, output_dir)

        # Create research info
        research_info = ResearchInfo(
            vector_store_name=vector_store_name or config.vector_store.name,
            vector_store_id=None,  # Will be resolved if needed
            temp_dir=temp_dir,
            output_dir=output_dir,
        )

        # Create trace processor
        trace_file = run_dir / "trace.json"
        trace_processor = BenchmarkTraceProcessor(str(trace_file))

        # Import and setup managers/servers
        from agentic_research.deep_research_manager import DeepResearchManager

        # Build MCP servers
        fs_server_params = self._build_fs_server_params(temp_dir, output_dir, config)
        fs_server = MCPServerStdio(
            name="FS_MCP_SERVER",
            params=fs_server_params,
            client_session_timeout_seconds=config.mcp.client_timeout_seconds,
        )

        dataprep_url = os.getenv(
            "MCP_DATAPREP_URL",
            f"http://{config.mcp.server_host}:{config.mcp.server_port}/sse",
        )
        dataprep_server = MCPServerSse(
            name="DATAPREP_MCP_SERVER",
            params={"url": dataprep_url, "timeout": config.mcp.http_timeout_seconds},
            client_session_timeout_seconds=config.mcp.client_timeout_seconds,
        )

        # Run workflow with trace processor
        print("  🚀 Running workflow...")
        async with fs_server, dataprep_server:
            manager = DeepResearchManager()

            # Install trace processor
            from agents import add_trace_processor

            add_trace_processor(trace_processor)

            await manager.run(
                fs_server=fs_server,
                dataprep_server=dataprep_server,
                vector_mcp_server=None,
                query=syllabus,
                research_info=research_info,
            )

        # Save trace
        trace_processor.save()
        print(f"  ✅ Trace saved: {trace_file}")

        # Analyze trace for metrics
        print("  📊 Analyzing trace...")
        analyzer = TraceAnalyzer(str(trace_file))
        timing = analyzer.extract_timing()
        agent_calls = analyzer.extract_agent_calls()

        # Find generated report
        report_file = self._find_report_file(output_dir)
        if not report_file:
            raise FileNotFoundError(f"No report found in {output_dir}")

        with open(report_file, encoding="utf-8") as f:
            report_markdown = f.read()

        # Evaluate quality (existing evaluator)
        print("  📝 Evaluating quality...")
        quality_result = await self._evaluate_quality(report_markdown)

        # Evaluate RAG Triad
        print("  🎯 Evaluating RAG Triad...")
        raw_notes = extract_raw_notes_from_report(report_markdown)
        rag_triad = await evaluate_rag_triad(report_markdown, raw_notes, syllabus)
        rag_triad_data = rag_triad.model_dump() if hasattr(rag_triad, "model_dump") else rag_triad
        print("  📏 Evaluating syllabus compliance...")
        spec_compliance = await evaluate_spec_compliance(report_markdown, syllabus, raw_notes)
        scores = compute_score_breakdown(
            spec_result=spec_compliance,
            quality_result=quality_result,
            rag_triad_average=rag_triad_data["average"],
            rag_context_relevance=rag_triad_data.get("context_relevance"),
            timing=timing.model_dump(),
            agent_calls=agent_calls.model_dump(),
        )

        # Compile results
        result = {
            "report_file": str(report_file),
            "report_path": str(report_file),
            "trace_file": str(trace_file),
            "timing": timing.model_dump(),
            "agent_calls": agent_calls.model_dump(),
            "quality_result": quality_result.model_dump(),
            "rag_triad": rag_triad_data,
            "spec_compliance": spec_compliance.model_dump(),
            "scores": scores.model_dump(),
        }

        # Save individual run result
        result_file = run_dir / "result.json"
        with open(result_file, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2)

        return result

    async def _evaluate_quality(self, report_markdown: str) -> any:
        """Evaluate report quality using LLM-as-a-judge."""
        judge_agent = Agent(
            name="quality_judge",
            instructions=llm_as_judge_prompt_v1,
            model="openai/gpt-4.1-mini",
            output_type=EvaluationResult,
        )

        result = await Runner.run(judge_agent, report_markdown)
        return result.final_output_as(EvaluationResult)

    def _detect_outliers(self, runs: list[dict], threshold: float = 1.5) -> list[int]:
        """
        Detect outlier runs based on timing.

        Args:
            runs: List of run results
            threshold: Outlier threshold (default: 1.5x median)

        Returns:
            List of outlier run indices
        """
        timings = [run["timing"]["total_seconds"] for run in runs]

        if len(timings) < 2:
            return []

        # Calculate median
        sorted_timings = sorted(timings)
        median = sorted_timings[len(sorted_timings) // 2]

        # Find outliers
        outliers = []
        for i, timing in enumerate(timings):
            if timing > median * threshold:
                outliers.append(i)

        return outliers

    def _compute_average(self, runs: list[dict]) -> dict:
        """Compute average metrics across runs."""
        if not runs:
            return {}

        # Average timing
        avg_timing = {
            "total_seconds": sum(r["timing"]["total_seconds"] for r in runs) / len(runs),
            "phases": {},
        }

        # Average phase timings
        for phase in runs[0]["timing"]["phases"].keys():
            avg_timing["phases"][phase] = sum(r["timing"]["phases"][phase] for r in runs) / len(
                runs
            )

        # Average agent calls
        avg_agent_calls = {}
        for key in runs[0]["agent_calls"].keys():
            avg_agent_calls[key] = sum(r["agent_calls"][key] for r in runs) / len(runs)

        # Average RAG Triad
        avg_rag_triad = {
            "groundedness": sum(r["rag_triad"]["groundedness"] for r in runs) / len(runs),
            "context_relevance": sum(r["rag_triad"]["context_relevance"] for r in runs) / len(runs),
            "answer_relevance": sum(r["rag_triad"]["answer_relevance"] for r in runs) / len(runs),
            "average": sum(r["rag_triad"]["average"] for r in runs) / len(runs),
        }

        avg_scores = {
            key: sum(r["scores"][key] for r in runs) / len(runs)
            for key in (
                "spec_compliance_100",
                "content_quality_100",
                "rag_compliance_100",
                "efficiency_100",
                "overall_100",
            )
        }
        avg_scores["analysis"] = runs[-1]["scores"].get("analysis", "")

        return {
            "timing": avg_timing,
            "agent_calls": avg_agent_calls,
            "rag_triad": avg_rag_triad,
            "scores": avg_scores,
        }

    def _load_syllabus(self, syllabus_file: str) -> str:
        """Load syllabus from file."""
        with open(syllabus_file, encoding="utf-8") as f:
            return f.read()

    def _find_report_file(self, output_dir: str) -> Path | None:
        """Find the generated report markdown file."""
        output_path = Path(output_dir)
        md_files = list(output_path.glob("*.md"))

        if md_files:
            # Return most recent
            return max(md_files, key=lambda p: p.stat().st_mtime)

        return None

    def _get_commit_hash(self) -> str:
        """Get current git commit hash."""
        try:
            return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"]).decode().strip()
        except Exception:
            return "unknown"

    def _build_fs_server_params(self, temp_dir: str, output_dir: str, config) -> dict:
        """Build filesystem MCP server params."""
        import shlex

        fs_command = os.getenv("MCP_FS_COMMAND")
        fs_args = os.getenv("MCP_FS_ARGS")
        # Keep only benchmark runtime roots to avoid exposing project source tree.
        allowed_dirs: list[str] = []
        for candidate in [temp_dir, output_dir]:
            real_candidate = os.path.realpath(candidate)
            if real_candidate not in allowed_dirs:
                allowed_dirs.append(real_candidate)

        if fs_command:
            args = shlex.split(fs_args) if fs_args else []
            args.extend(allowed_dirs)
        else:
            fs_command = "npx"
            args = ["-y", "@modelcontextprotocol/server-filesystem", *allowed_dirs]

        return {"command": fs_command, "args": args}

    def _normalize_runtime_paths(self, temp_dir: str, output_dir: str) -> tuple[str, str]:
        """
        Normalize runtime directories to canonical real paths.
        Avoid /var vs /private/var mismatches with filesystem MCP allowed roots.
        """
        return os.path.realpath(temp_dir), os.path.realpath(output_dir)

    def _build_vector_mcp_server(self, config):
        """Build vector MCP server for Chroma."""
        from agents.mcp import MCPServerStdio

        allowlist = set(config.vector_mcp.tool_allowlist)

        def chroma_tool_filter(_context, tool):
            return tool.name in allowlist

        chroma_env = dict(os.environ)
        chroma_env.update(
            {
                "ANONYMIZED_TELEMETRY": "False",
                "HTTPX_LOG_LEVEL": "ERROR",
                "HTTPCORE_LOG_LEVEL": "ERROR",
                "FASTMCP_LOG_LEVEL": "ERROR",
            }
        )
        # Some existing Chroma collections store OPENAI_API_KEY as api_key_env_var.
        # If only CHROMA_OPENAI_API_KEY is set, mirror it for compatibility.
        if chroma_env.get("CHROMA_OPENAI_API_KEY") and not chroma_env.get("OPENAI_API_KEY"):
            chroma_env["OPENAI_API_KEY"] = chroma_env["CHROMA_OPENAI_API_KEY"]

        return MCPServerStdio(
            name="CHROMA_MCP_SERVER",
            params={
                "command": config.vector_mcp.command,
                "args": config.vector_mcp.args,
                "env": chroma_env,
            },
            tool_filter=chroma_tool_filter,
            cache_tools_list=True,
            client_session_timeout_seconds=config.vector_mcp.client_timeout_seconds,
        )


async def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Run model setup benchmark")
    parser.add_argument(
        "--config",
        default="configs/config-docker-dgx.yaml",
        help="Config file (default: configs/config-docker-dgx.yaml)",
    )
    parser.add_argument(
        "--syllabus",
        required=True,
        help="Syllabus/query file (e.g., test_files/query_advanced_1.md)",
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=2,
        help="Number of runs (default: 2)",
    )
    parser.add_argument(
        "--output",
        default="benchmarks",
        help="Output directory (default: benchmarks)",
    )
    parser.add_argument(
        "--vector-store-name",
        help="Vector store name (for Chroma)",
    )

    args = parser.parse_args()

    runner = BenchmarkRunner(output_dir=args.output)

    result = await runner.run_benchmark(
        config_file=args.config,
        syllabus_file=args.syllabus,
        num_runs=args.runs,
        vector_store_name=args.vector_store_name,
    )

    print("\n" + "=" * 60)
    print("🎉 BENCHMARK COMPLETED")
    print("=" * 60)
    print(f"Setup: {result['setup_metadata']['setup_name']}")
    print(f"Average timing: {result['average']['timing']['total_seconds']:.1f}s")
    avg_quality = runner._quality_tier_from_score(
        result["average"]["scores"]["content_quality_100"]
    )
    print(f"Average quality: {avg_quality}")
    print(f"Average RAG Triad: {result['average']['rag_triad']['average']:.2f}")
    print(f"Average overall score: {result['average']['scores']['overall_100']:.1f}/100")
    print(f"Average spec compliance: {result['average']['scores']['spec_compliance_100']:.1f}/100")
    print(f"Average content quality: {result['average']['scores']['content_quality_100']:.1f}/100")
    print(f"Average RAG compliance: {result['average']['scores']['rag_compliance_100']:.1f}/100")
    print(f"Average efficiency: {result['average']['scores']['efficiency_100']:.1f}/100")
    print(f"Analysis: {result['average']['scores']['analysis']}")


def cli_main():
    """Synchronous CLI entry point (for poetry scripts)."""
    asyncio.run(main())


if __name__ == "__main__":
    cli_main()
