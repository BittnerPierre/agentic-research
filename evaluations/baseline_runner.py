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
"""

import argparse
import asyncio
import json
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional

import yaml
from agents.mcp import MCPServerStdio

from src.agents.schemas import ResearchInfo

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

        Args:
            test_case_name: Name of test case (without .yaml)

        Returns:
            Test case dictionary

        Raises:
            FileNotFoundError: If test case not found
        """
        test_case_file = self.test_cases_dir / f"{test_case_name}.yaml"

        if not test_case_file.exists():
            raise FileNotFoundError(
                f"Test case not found: {test_case_file}\n"
                f"Available: {list(self.test_cases_dir.glob('*.yaml'))}"
            )

        with open(test_case_file, "r", encoding="utf-8") as f:
            test_case = yaml.safe_load(f)

        return test_case

    async def run_evaluation(
        self, test_case: dict, vector_store_id: Optional[str] = None
    ) -> dict:
        """
        Run evaluation for test case.

        Args:
            test_case: Test case dictionary
            vector_store_id: Vector store ID (optional)

        Returns:
            Evaluation results dictionary
        """
        # Extract syllabus from test case
        syllabus = test_case.get("syllabus") or test_case.get("query")

        if not syllabus:
            raise ValueError("Test case missing 'syllabus' or 'query'")

        # Create temp/output directories
        temp_dir = tempfile.mkdtemp(prefix="eval_")
        output_dir = tempfile.mkdtemp(prefix="eval_output_")

        # Create ResearchInfo
        research_info = ResearchInfo(
            vector_store_id=vector_store_id or "vs_test_123",
            temp_dir=temp_dir,
            output_dir=output_dir,
        )

        # Create MCP servers
        fs_server = MCPServerStdio(
            "npx",
            ["-y", "@modelcontextprotocol/server-filesystem", temp_dir, output_dir],
        )

        dataprep_server = MCPServerStdio(
            "npx",
            ["-y", "@bpitman/mcp-server-openai"],
        )

        # Run evaluation
        async with fs_server.connect(), dataprep_server.connect():
            evaluator = FullWorkflowEvaluator(
                output_dir="evaluations/full_workflow_results"
            )

            results = await evaluator.run(
                fs_server=fs_server,
                dataprep_server=dataprep_server,
                research_info=research_info,
                syllabus=syllabus,
            )

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

        return validation

    def save_baseline(
        self, test_case_name: str, results: dict, commit_hash: Optional[str] = None
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

        with open(baseline_path, "r", encoding="utf-8") as f:
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
        "--vector-store-id",
        type=str,
        help="Vector store ID",
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
    print(f"\n🚀 Running evaluation...")
    results = await runner.run_evaluation(test_case, args.vector_store_id)

    # Validate against test case
    print(f"\n✅ Validating results...")
    validation = runner.validate_against_test_case(results, test_case)

    print(f"\n=== VALIDATION RESULTS ===")
    print(f"Overall: {'✅ PASS' if validation['overall_pass'] else '❌ FAIL'}")
    for check_name, check_result in validation["checks"].items():
        status = "✅" if check_result["passed"] else "❌"
        print(
            f"  {status} {check_name}: {check_result['actual']} (expected: {check_result['expected']})"
        )

    # Save baseline if requested
    if args.save_baseline:
        print(f"\n💾 Saving baseline...")
        baseline_file = runner.save_baseline(
            args.test_case, results, args.commit_hash
        )

    # Compare against baseline if requested
    if args.compare_baseline:
        print(f"\n📊 Comparing against baseline...")
        baseline = runner.load_baseline(args.compare_baseline)
        comparison = runner.compare_against_baseline(results, baseline, test_case)

        print(f"\n=== BASELINE COMPARISON ===")
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
