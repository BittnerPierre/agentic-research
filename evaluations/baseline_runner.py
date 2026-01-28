"""
Baseline Runner - Execute and Compare Evaluations

Runs evaluation against test cases and saves baseline results.
Supports regression testing by comparing against previous baselines.

Usage:
    # Run and save new baseline
    poetry run baseline-eval --test-case trivial_research --save-baseline

    # Compare against baseline
    poetry run baseline-eval --test-case trivial_research --compare-baseline baseline_trivial_<commit>.json

    # Run without saving
    poetry run baseline-eval --test-case trivial_research

    # Use a specific config
    poetry run baseline-eval --test-case trivial_research --config configs/config-gpt-4.1-mini.yaml
"""

import argparse
import asyncio
import json
import os
import tempfile
from datetime import datetime
from pathlib import Path

from agentic_research.agents.schemas import ResearchInfo
from agentic_research.config import get_config
from agents.mcp import MCPServerSse, MCPServerStdio

from .eval_utils import build_fs_server_params, load_test_case as load_test_case_yaml
from .full_workflow_evaluator import FullWorkflowEvaluator


class BaselineRunner:
    """
    Runs evaluation and manages baselines.
    """

    def __init__(self, test_cases_dir: str = "evaluations/test_cases"):
        self.test_cases_dir = Path(test_cases_dir)
        self.baselines_dir = Path("evaluations/baselines")
        self.baselines_dir.mkdir(parents=True, exist_ok=True)

    def load_test_case(self, test_case_name: str) -> dict:
        """
        Load test case YAML.
        """
        return load_test_case_yaml(test_case_name, test_cases_dir=str(self.test_cases_dir))

    async def run_evaluation(
        self,
        test_case: dict,
        vector_store_name: str,
        vector_store_id: str | None = None,
        config_file: str = "config.yaml",
    ) -> dict:
        """
        Run evaluation for test case.

        Args:
            test_case: Test case dictionary
            vector_store_name: Vector store name to lookup/create
            vector_store_id: Vector store ID (optional, for testing with specific data - overrides name)

        Returns:
            Evaluation results dictionary
        """
        config = get_config(config_file)

        # Extract syllabus from test case
        syllabus = test_case.get("syllabus") or test_case.get("query")

        if not syllabus:
            raise ValueError("Test case missing 'syllabus' or 'query'")

        provider = config.vector_search.provider
        resolved_vector_store_id = vector_store_id

        # Storage resolution: only needed for OpenAI file_search
        if provider == "openai":
            if resolved_vector_store_id is None:
                print(f"🔍 Looking up storage: '{vector_store_name}'")

                from openai import OpenAI

                client = OpenAI()

                # Lookup vector store by name (inline to avoid cross-module imports)
                vector_stores = client.vector_stores.list()
                for vs in vector_stores:
                    if vs.name == vector_store_name:
                        resolved_vector_store_id = vs.id
                        break

                if resolved_vector_store_id is None:
                    print(f"📦 Creating new storage: '{vector_store_name}'")
                    vector_store_obj = client.vector_stores.create(name=vector_store_name)
                    resolved_vector_store_id = vector_store_obj.id
                    print(f"✅ Storage created: {resolved_vector_store_id}")
                else:
                    print(f"✅ Found existing storage: {resolved_vector_store_id}")
            else:
                print(f"✅ Using provided storage ID: {resolved_vector_store_id}")
        else:
            if resolved_vector_store_id is not None:
                print(f"✅ Using provided storage ID: {resolved_vector_store_id}")
            else:
                print(f"🔍 Using non-OpenAI provider '{provider}' with store name: '{vector_store_name}'")

        # Create temp/output directories
        temp_dir = tempfile.mkdtemp(prefix="eval_")
        output_dir = tempfile.mkdtemp(prefix="eval_output_")

        # Create ResearchInfo
        research_info = ResearchInfo(
            vector_store_name=vector_store_name,
            vector_store_id=resolved_vector_store_id,
            temp_dir=temp_dir,
            output_dir=output_dir,
        )

        # Create MCP servers
        fs_server = MCPServerStdio(
            name="FS_MCP_SERVER",
            params=build_fs_server_params(temp_dir, output_dir),
        )

        dataprep_url = os.getenv(
            "MCP_DATAPREP_URL",
            f"http://{config.mcp.server_host}:{config.mcp.server_port}/sse",
        )
        dataprep_server = MCPServerSse(
            name="DATAPREP_MCP_SERVER",
            params={
                "url": dataprep_url,
                "timeout": config.mcp.http_timeout_seconds,
            },
            client_session_timeout_seconds=config.mcp.client_timeout_seconds,
        )

        # Run evaluation
        async with fs_server, dataprep_server:
            evaluator = FullWorkflowEvaluator(
                output_dir="evaluations/full_workflow_results",
                config_file=config_file,
            )

            results = await evaluator.run(
                fs_server=fs_server,
                dataprep_server=dataprep_server,
                research_info=research_info,
                syllabus=syllabus,
                test_case=test_case,
            )

        results["config_file"] = config_file
        results["config_name"] = config.config_name
        return results

    def validate_against_test_case(self, results: dict, test_case: dict) -> dict:
        """
        Validate results against test case expectations.

        Args:
            results: Evaluation results
            test_case: Test case with expected outcomes

        Returns:
            Validation report with PASS/FAIL
        """
        expected = test_case.get("expected_outcomes", {})
        quality = results["quality_result"]
        grades = quality["grades"]

        validation = {
            "test_case": test_case["name"],
            "timestamp": datetime.now().isoformat(),
            "overall_pass": True,
            "checks": {},
        }

        # Prefer validating against the full markdown report if available
        report_content = results.get("report_summary", "") or ""
        report_path = results.get("report_path")
        if report_path:
            try:
                report_content = Path(report_path).read_text(encoding="utf-8")
            except Exception:
                # Fall back to summary if file can't be read
                pass

        # Check minimum grades
        min_grades = test_case.get("min_grades", {})
        grade_order = {"A": 5, "B": 4, "C": 3, "D": 2, "E": 1}

        for dimension, min_grade in min_grades.items():
            actual_grade = grades.get(dimension)
            passed = grade_order.get(actual_grade, 0) >= grade_order.get(min_grade, 0)

            validation["checks"][f"min_grade_{dimension}"] = {
                "expected": f">= {min_grade}",
                "actual": actual_grade,
                "passed": passed,
            }

            if not passed:
                validation["overall_pass"] = False

        # Check judgment
        acceptable = test_case.get("acceptable_judgments", ["PASS"])
        judgment = quality["judgment"]
        judgment_passed = judgment in acceptable

        validation["checks"]["judgment"] = {
            "expected": f"in {acceptable}",
            "actual": judgment,
            "passed": judgment_passed,
        }

        if not judgment_passed:
            validation["overall_pass"] = False

        # Check required sections (if specified)
        required_sections = expected.get("required_sections", [])
        if required_sections:
            missing_sections = []
            for section in required_sections:
                if section not in report_content:
                    missing_sections.append(section)

            sections_passed = len(missing_sections) == 0
            validation["checks"]["required_sections"] = {
                "expected": f"contains {required_sections}",
                "actual": f"missing: {missing_sections}" if missing_sections else "all present",
                "passed": sections_passed,
            }

            if not sections_passed:
                validation["overall_pass"] = False

        # Check required report headers (if specified)
        required_report_headers = expected.get("required_report_headers", [])
        if required_report_headers:
            missing_headers = []
            for header in required_report_headers:
                if header not in report_content:
                    missing_headers.append(header)

            headers_passed = len(missing_headers) == 0
            validation["checks"]["required_report_headers"] = {
                "expected": f"contains {required_report_headers}",
                "actual": f"missing: {missing_headers}" if missing_headers else "all present",
                "passed": headers_passed,
            }

            if not headers_passed:
                validation["overall_pass"] = False

        # Check word count (if specified)
        min_word_count = expected.get("min_word_count")
        max_word_count = expected.get("max_word_count")

        if min_word_count or max_word_count:
            word_count = len(report_content.split())

            if min_word_count:
                min_passed = word_count >= min_word_count
                validation["checks"]["min_word_count"] = {
                    "expected": f">= {min_word_count}",
                    "actual": word_count,
                    "passed": min_passed,
                }
                if not min_passed:
                    validation["overall_pass"] = False

            if max_word_count:
                max_passed = word_count <= max_word_count
                validation["checks"]["max_word_count"] = {
                    "expected": f"<= {max_word_count}",
                    "actual": word_count,
                    "passed": max_passed,
                }
                if not max_passed:
                    validation["overall_pass"] = False

        # Check must-mention algorithms (if specified)
        must_mention_algorithms = expected.get("must_mention_algorithms", [])
        if must_mention_algorithms:
            missing_algorithms = []
            for algo in must_mention_algorithms:
                if algo not in report_content:
                    missing_algorithms.append(algo)

            algos_passed = len(missing_algorithms) == 0
            validation["checks"]["must_mention_algorithms"] = {
                "expected": f"mentions {must_mention_algorithms}",
                "actual": f"missing: {missing_algorithms}" if missing_algorithms else "all present",
                "passed": algos_passed,
            }

            if not algos_passed:
                validation["overall_pass"] = False

        # Check must-mention concepts (if specified)
        must_mention_concepts = expected.get("must_mention_concepts", [])
        if must_mention_concepts:
            missing_concepts = []
            for concept in must_mention_concepts:
                if concept not in report_content:
                    missing_concepts.append(concept)

            concepts_passed = len(missing_concepts) == 0
            validation["checks"]["must_mention_concepts"] = {
                "expected": f"mentions {must_mention_concepts}",
                "actual": f"missing: {missing_concepts}" if missing_concepts else "all present",
                "passed": concepts_passed,
            }

            if not concepts_passed:
                validation["overall_pass"] = False

        # Check minimum sources (if specified)
        min_sources = expected.get("min_sources")
        sources_count = results.get("sources_read_count")
        if sources_count is None:
            sources_count = results.get("sources_count")
        if sources_count is None:
            sources = results.get("sources_read")
            if isinstance(sources, list):
                sources_count = len(sources)
        if sources_count is None:
            sources = results.get("sources")
            if isinstance(sources, list):
                sources_count = len(sources)

        if min_sources is not None and sources_count is not None:
            sources_passed = sources_count >= min_sources
            validation["checks"]["min_sources"] = {
                "expected": f">= {min_sources}",
                "actual": sources_count,
                "passed": sources_passed,
            }
            if not sources_passed:
                validation["overall_pass"] = False

        # Check topics covered (if specified)
        topics_covered = expected.get("topics_covered", [])
        if topics_covered:
            missing_topics = []
            for topic in topics_covered:
                if topic not in report_content:
                    missing_topics.append(topic)

            topics_passed = len(missing_topics) == 0
            validation["checks"]["topics_covered"] = {
                "expected": f"covers {topics_covered}",
                "actual": f"missing: {missing_topics}" if missing_topics else "all present",
                "passed": topics_passed,
            }

            if not topics_passed:
                validation["overall_pass"] = False

        # Check keywords present (if specified)
        keywords_present = expected.get("keywords_present", [])
        if keywords_present:
            keyword_found = any(keyword in report_content for keyword in keywords_present)
            validation["checks"]["keywords_present"] = {
                "expected": f"contains one of {keywords_present}",
                "actual": "found" if keyword_found else "missing",
                "passed": keyword_found,
            }

            if not keyword_found:
                validation["overall_pass"] = False

        return validation

    def save_baseline(
        self,
        test_case_name: str,
        results: dict,
        commit_hash: str | None = None,
        config_file: str = "config.yaml",
    ) -> str:
        """
        Save evaluation results as baseline.

        Args:
            test_case_name: Name of test case
            results: Evaluation results
            commit_hash: Git commit hash (optional)

        Returns:
            Path to saved baseline file
        """
        if not commit_hash:
            # Try to get current commit hash
            import subprocess

            try:
                commit_hash = (
                    subprocess.check_output(["git", "rev-parse", "--short", "HEAD"])
                    .decode()
                    .strip()
                )
            except Exception:
                commit_hash = "unknown"

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        baseline_file = (
            self.baselines_dir / f"baseline_{test_case_name}_{commit_hash}_{timestamp}.json"
        )

        baseline_data = {
            "test_case": test_case_name,
            "config_file": config_file,
            "config_name": results.get("config_name"),
            "commit_hash": commit_hash,
            "timestamp": timestamp,
            "results": results,
        }

        with open(baseline_file, "w", encoding="utf-8") as f:
            json.dump(baseline_data, f, indent=2)

        print(f"✅ Baseline saved: {baseline_file}")

        return str(baseline_file)

    def load_baseline(self, baseline_file: str) -> dict:
        """
        Load baseline from file.

        Args:
            baseline_file: Path to baseline JSON

        Returns:
            Baseline data

        Raises:
            FileNotFoundError: If baseline not found
        """
        baseline_path = Path(baseline_file)

        if not baseline_path.is_absolute():
            # Try relative to baselines_dir
            baseline_path = self.baselines_dir / baseline_file

        if not baseline_path.exists():
            raise FileNotFoundError(f"Baseline not found: {baseline_path}")

        with open(baseline_path, encoding="utf-8") as f:
            baseline = json.load(f)

        return baseline

    def compare_against_baseline(
        self, current_results: dict, baseline: dict, test_case: dict
    ) -> dict:
        """
        Compare current results against baseline.

        Args:
            current_results: Current evaluation results
            baseline: Baseline data
            test_case: Test case with degradation thresholds

        Returns:
            Comparison report with degradation detection
        """
        baseline_results = baseline["results"]
        current_quality = current_results["quality_result"]
        baseline_quality = baseline_results["quality_result"]

        comparison = {
            "baseline_commit": baseline.get("commit_hash", "unknown"),
            "baseline_timestamp": baseline.get("timestamp", "unknown"),
            "current_timestamp": datetime.now().isoformat(),
            "degradation_detected": False,
            "comparisons": {},
        }

        # Compare grades
        grade_order = {"A": 5, "B": 4, "C": 3, "D": 2, "E": 1}
        max_drop = test_case.get("baseline", {}).get("max_degradation", {}).get("grade_drop", 1)

        for dimension in ["format", "grounding", "agenda", "usability"]:
            current_grade = current_quality["grades"].get(dimension)
            baseline_grade = baseline_quality["grades"].get(dimension)

            current_score = grade_order.get(current_grade, 0)
            baseline_score = grade_order.get(baseline_grade, 0)

            drop = baseline_score - current_score
            degraded = drop > max_drop

            comparison["comparisons"][f"grade_{dimension}"] = {
                "baseline": baseline_grade,
                "current": current_grade,
                "drop": drop,
                "max_allowed_drop": max_drop,
                "degraded": degraded,
            }

            if degraded:
                comparison["degradation_detected"] = True

        # Compare judgment
        current_judgment = current_quality["judgment"]
        baseline_judgment = baseline_quality["judgment"]

        judgment_worse = (
            (baseline_judgment == "PASS" and current_judgment != "PASS")
            or (baseline_judgment == "BORDERLINE" and current_judgment == "FAIL")
        )

        comparison["comparisons"]["judgment"] = {
            "baseline": baseline_judgment,
            "current": current_judgment,
            "degraded": judgment_worse,
        }

        if judgment_worse:
            comparison["degradation_detected"] = True

        return comparison


async def main():
    """
    CLI entry point for baseline evaluation.
    """
    parser = argparse.ArgumentParser(description="Run baseline evaluation")
    parser.add_argument(
        "--test-case",
        type=str,
        required=True,
        help="Test case name (e.g., trivial_research)",
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
        "--config",
        type=str,
        default="config.yaml",
        help="Config file to use (e.g., 'configs/config-gpt-4.1-mini.yaml')",
    )
    parser.add_argument(
        "--save-baseline",
        action="store_true",
        help="Save results as new baseline",
    )
    parser.add_argument(
        "--compare-baseline",
        type=str,
        help="Compare against baseline file",
    )
    parser.add_argument(
        "--commit-hash",
        type=str,
        help="Git commit hash for baseline filename",
    )

    args = parser.parse_args()

    runner = BaselineRunner()

    # Load test case
    print(f"📋 Loading test case: {args.test_case}")
    test_case = runner.load_test_case(args.test_case)
    print(f"   Description: {test_case.get('description', 'N/A')}")

    # Run evaluation
    print("\n🚀 Running evaluation...")
    results = await runner.run_evaluation(
        test_case,
        vector_store_name=args.vector_store_name,
        vector_store_id=args.vector_store_id,
        config_file=args.config,
    )

    # Validate against test case
    print("\n✅ Validating results...")
    validation = runner.validate_against_test_case(results, test_case)

    print("\n=== VALIDATION RESULTS ===")
    print(f"Overall: {'✅ PASS' if validation['overall_pass'] else '❌ FAIL'}")
    for check_name, check_result in validation["checks"].items():
        status = "✅" if check_result["passed"] else "❌"
        print(
            f"  {status} {check_name}: {check_result['actual']} (expected: {check_result['expected']})"
        )

    # Save baseline if requested
    if args.save_baseline:
        print("\n💾 Saving baseline...")
        baseline_file = runner.save_baseline(
            args.test_case,
            results,
            args.commit_hash,
            config_file=args.config,
        )
        print(f"Baseline saved: {baseline_file}")

    # Compare against baseline if requested
    if args.compare_baseline:
        print("\n📊 Comparing against baseline...")
        baseline = runner.load_baseline(args.compare_baseline)
        comparison = runner.compare_against_baseline(results, baseline, test_case)

        print("\n=== BASELINE COMPARISON ===")
        print(f"Baseline: {comparison['baseline_commit']} @ {comparison['baseline_timestamp']}")
        print(
            f"Degradation: {'❌ DETECTED' if comparison['degradation_detected'] else '✅ NONE'}"
        )

        for comp_name, comp_result in comparison["comparisons"].items():
            if "degraded" in comp_result:
                status = "❌" if comp_result["degraded"] else "✅"
                print(f"  {status} {comp_name}:")
                print(f"     Baseline: {comp_result['baseline']}")
                print(f"     Current:  {comp_result['current']}")

    print("\n=== SUMMARY ===")
    print(f"Report: {results['report_file']}")
    print(f"Judgment: {results['quality_result']['judgment']}")
    print(f"Grades: {results['quality_result']['grades']}")


def cli_main():
    """
    Synchronous CLI entry point (for poetry scripts).
    """
    asyncio.run(main())


if __name__ == "__main__":
    cli_main()
