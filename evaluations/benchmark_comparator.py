"""
Benchmark Comparator - Compare and visualize benchmark results

Aggregates results from multiple setup benchmarks and generates
comparison tables in Markdown format.
"""

import argparse
import json
from pathlib import Path


class BenchmarkComparator:
    """
    Compares benchmark results across model setups.

    Generates Markdown tables with metrics comparison.
    """

    def __init__(self, benchmark_dir: str):
        """
        Initialize comparator.

        Args:
            benchmark_dir: Directory containing benchmark results
                          (e.g., benchmarks/run_20260211_143022/)
        """
        self.benchmark_dir = Path(benchmark_dir)

        if not self.benchmark_dir.exists():
            raise FileNotFoundError(f"Benchmark directory not found: {benchmark_dir}")

    def compare(self) -> str:
        """
        Compare all benchmarks and generate Markdown report.

        Returns:
            Markdown formatted comparison table
        """
        # 1. Load all benchmark results
        benchmarks = self._load_benchmarks()

        if not benchmarks:
            return "No benchmarks found in directory."

        # 2. Generate comparison tables
        markdown = self._generate_markdown(benchmarks)

        # 3. Save to file
        output_file = self.benchmark_dir / "comparison_table.md"
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(markdown)

        print(f"✅ Comparison table saved: {output_file}")

        return markdown

    def _load_benchmarks(self) -> list[dict]:
        """Load all benchmark results from directory."""
        benchmarks = []

        # Find all benchmark_result.json files in subdirectories
        for result_file in self.benchmark_dir.glob("*/benchmark_result.json"):
            try:
                with open(result_file, encoding="utf-8") as f:
                    data = json.load(f)
                    benchmarks.append(data)
            except Exception as e:
                print(f"⚠️  Failed to load {result_file}: {e}")

        return benchmarks

    def _generate_markdown(self, benchmarks: list[dict]) -> str:
        """Generate Markdown comparison report."""
        lines = [
            "# Benchmark Comparison Report",
            "",
            f"**Date**: {benchmarks[0].get('timestamp', 'N/A')}",
            f"**Setups compared**: {len(benchmarks)}",
            "",
            "---",
            "",
        ]

        # Summary Table
        lines.extend(self._generate_summary_table(benchmarks))
        lines.append("")

        # Detailed Timing Table
        lines.extend(self._generate_timing_table(benchmarks))
        lines.append("")

        # RAG Triad Table
        lines.extend(self._generate_rag_triad_table(benchmarks))
        lines.append("")

        # Quality Grades Table
        lines.extend(self._generate_quality_table(benchmarks))
        lines.append("")

        # Best Performers
        lines.extend(self._generate_best_performers(benchmarks))
        lines.append("")

        # Recommendations
        lines.extend(self._generate_recommendations(benchmarks))

        return "\n".join(lines)

    def _generate_summary_table(self, benchmarks: list[dict]) -> list[str]:
        """Generate main summary comparison table."""
        lines = [
            "## Summary Table",
            "",
            "| Setup | Avg Time (s) | Grades (F/G/A/U) | Judgment | RAG Triad (G/C/A) | Agent Calls | Status |",
            "|-------|--------------|------------------|----------|-------------------|-------------|---------|",
        ]

        for bench in sorted(benchmarks, key=lambda b: b["setup_metadata"]["setup_name"]):
            setup_name = bench["setup_metadata"]["setup_name"]
            avg = bench["average"]

            # Timing
            avg_time = f"{avg['timing']['total_seconds']:.1f}"

            # Grades
            quality = bench["runs"][0]["quality_result"]
            grades = quality["grades"]
            grades_str = f"{grades['format']}/{grades['grounding']}/{grades['agenda']}/{grades['usability']}"

            # Judgment
            judgment = quality["judgment"]

            # RAG Triad
            rag = avg["rag_triad"]
            rag_str = f"{rag['groundedness']:.2f}/{rag['context_relevance']:.2f}/{rag['answer_relevance']:.2f}"

            # Agent calls
            agent_calls = int(avg["agent_calls"]["total"])

            # Status
            status = self._get_status(bench, benchmarks)

            lines.append(
                f"| {setup_name} | {avg_time} | {grades_str} | {judgment} | {rag_str} | {agent_calls} | {status} |"
            )

        return lines

    def _generate_timing_table(self, benchmarks: list[dict]) -> list[str]:
        """Generate detailed timing breakdown table."""
        lines = [
            "## Detailed Timing Breakdown",
            "",
            "| Setup | Prep (s) | Plan (s) | Search (s) | Write (s) | Total (s) |",
            "|-------|----------|----------|------------|-----------|-----------|",
        ]

        for bench in sorted(benchmarks, key=lambda b: b["setup_metadata"]["setup_name"]):
            setup_name = bench["setup_metadata"]["setup_name"]
            avg = bench["average"]["timing"]

            prep = f"{avg['phases']['knowledge_preparation']:.1f}"
            plan = f"{avg['phases']['planning']:.1f}"
            search = f"{avg['phases']['search']:.1f}"
            write = f"{avg['phases']['writing']:.1f}"
            total = f"{avg['total_seconds']:.1f}"

            lines.append(f"| {setup_name} | {prep} | {plan} | {search} | {write} | {total} |")

        return lines

    def _generate_rag_triad_table(self, benchmarks: list[dict]) -> list[str]:
        """Generate RAG Triad scores table."""
        lines = [
            "## RAG Triad Scores",
            "",
            "| Setup | Groundedness | Context Relevance | Answer Relevance | Average |",
            "|-------|--------------|-------------------|------------------|---------|",
        ]

        for bench in sorted(benchmarks, key=lambda b: b["setup_metadata"]["setup_name"]):
            setup_name = bench["setup_metadata"]["setup_name"]
            rag = bench["average"]["rag_triad"]

            g = f"{rag['groundedness']:.3f}"
            c = f"{rag['context_relevance']:.3f}"
            a = f"{rag['answer_relevance']:.3f}"
            avg = f"{rag['average']:.3f}"

            lines.append(f"| {setup_name} | {g} | {c} | {a} | {avg} |")

        return lines

    def _generate_quality_table(self, benchmarks: list[dict]) -> list[str]:
        """Generate quality grades table."""
        lines = [
            "## Quality Grades",
            "",
            "| Setup | Format | Grounding | Agenda | Usability | Judgment |",
            "|-------|--------|-----------|--------|-----------|----------|",
        ]

        for bench in sorted(benchmarks, key=lambda b: b["setup_metadata"]["setup_name"]):
            setup_name = bench["setup_metadata"]["setup_name"]
            quality = bench["runs"][0]["quality_result"]
            grades = quality["grades"]

            lines.append(
                f"| {setup_name} | {grades['format']} | {grades['grounding']} | "
                f"{grades['agenda']} | {grades['usability']} | {quality['judgment']} |"
            )

        return lines

    def _generate_best_performers(self, benchmarks: list[dict]) -> list[str]:
        """Identify and list best performers by category."""
        lines = ["## Best Performers", ""]

        # Fastest
        fastest = min(benchmarks, key=lambda b: b["average"]["timing"]["total_seconds"])
        lines.append(
            f"- **Fastest**: {fastest['setup_metadata']['setup_name']} "
            f"({fastest['average']['timing']['total_seconds']:.1f}s)"
        )

        # Best RAG Triad
        best_rag = max(benchmarks, key=lambda b: b["average"]["rag_triad"]["average"])
        lines.append(
            f"- **Best RAG Triad**: {best_rag['setup_metadata']['setup_name']} "
            f"(avg: {best_rag['average']['rag_triad']['average']:.3f})"
        )

        # Best quality (count A/B grades)
        def quality_score(bench):
            grades = bench["runs"][0]["quality_result"]["grades"]
            return sum(
                1 for g in [grades["format"], grades["grounding"], grades["agenda"], grades["usability"]]
                if g in ("A", "B")
            )

        best_quality = max(benchmarks, key=quality_score)
        lines.append(
            f"- **Best Quality**: {best_quality['setup_metadata']['setup_name']} "
            f"(Judgment: {best_quality['runs'][0]['quality_result']['judgment']})"
        )

        # Most efficient (fewest calls)
        most_efficient = min(benchmarks, key=lambda b: b["average"]["agent_calls"]["total"])
        lines.append(
            f"- **Most Efficient**: {most_efficient['setup_metadata']['setup_name']} "
            f"({int(most_efficient['average']['agent_calls']['total'])} agent calls)"
        )

        return lines

    def _generate_recommendations(self, benchmarks: list[dict]) -> list[str]:
        """Generate recommendations based on results."""
        lines = ["## Recommendations", ""]

        # Find fastest
        fastest = min(benchmarks, key=lambda b: b["average"]["timing"]["total_seconds"])

        # Find best quality
        def quality_score(bench):
            grades = bench["runs"][0]["quality_result"]["grades"]
            return sum(
                1 for g in [grades["format"], grades["grounding"], grades["agenda"], grades["usability"]]
                if g in ("A", "B")
            )

        best_quality = max(benchmarks, key=quality_score)

        # Find best RAG
        best_rag = max(benchmarks, key=lambda b: b["average"]["rag_triad"]["average"])

        lines.append(
            f"1. **For speed-critical applications**: "
            f"Use **{fastest['setup_metadata']['setup_name']}** "
            f"({fastest['average']['timing']['total_seconds']:.1f}s average)"
        )

        lines.append(
            f"2. **For highest quality reports**: "
            f"Use **{best_quality['setup_metadata']['setup_name']}** "
            f"(Judgment: {best_quality['runs'][0]['quality_result']['judgment']})"
        )

        lines.append(
            f"3. **For best RAG performance**: "
            f"Use **{best_rag['setup_metadata']['setup_name']}** "
            f"(RAG Triad: {best_rag['average']['rag_triad']['average']:.3f})"
        )

        # Overall recommendation
        lines.append("")
        lines.append(
            "**Overall recommendation**: Consider the trade-offs between speed, "
            "quality, and RAG performance based on your use case."
        )

        return lines

    def _get_status(self, bench: dict, all_benchmarks: list[dict]) -> str:
        """Determine status emoji for a benchmark."""
        avg_time = bench["average"]["timing"]["total_seconds"]

        # Calculate median time
        all_times = [b["average"]["timing"]["total_seconds"] for b in all_benchmarks]
        median_time = sorted(all_times)[len(all_times) // 2]

        # Check quality
        judgment = bench["runs"][0]["quality_result"]["judgment"]

        if judgment != "PASS":
            return "⚠️ Quality"
        elif avg_time > median_time * 1.3:
            return "⚠️ Slow"
        elif avg_time < median_time * 0.8:
            return "✅ Fast"
        else:
            return "✅"


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Compare benchmark results")
    parser.add_argument(
        "--benchmark-dir",
        required=True,
        help="Directory containing benchmark results (e.g., benchmarks/run_20260211_143022/)",
    )
    parser.add_argument(
        "--output",
        help="Output file (default: benchmark_dir/comparison_table.md)",
    )

    args = parser.parse_args()

    comparator = BenchmarkComparator(args.benchmark_dir)
    markdown = comparator.compare()

    # Print to console
    print("\n" + "="*60)
    print(markdown)
    print("="*60)


if __name__ == "__main__":
    main()
