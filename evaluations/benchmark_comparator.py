"""
Benchmark Comparator - Compare and visualize benchmark results

Aggregates results from multiple setup benchmarks and generates
comparison tables in Markdown format.
"""

import argparse
import json
from collections import Counter
from pathlib import Path

GRADE_TO_SCORE = {
    "A": 100.0,
    "B": 85.0,
    "C": 70.0,
    "D": 50.0,
    "E": 30.0,
}

SCORE_TO_GRADE = [
    (95.0, "A"),
    (80.0, "B"),
    (65.0, "C"),
    (45.0, "D"),
    (0.0, "E"),
]


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
        all_runs = [self._bench_num_runs(bench) for bench in benchmarks]
        all_syllabi = sorted(
            {
                bench.get("syllabus_file", "N/A")
                for bench in benchmarks
                if bench.get("syllabus_file", "N/A")
            }
        )

        lines = [
            "# Benchmark Comparison Report",
            "",
            f"**Date**: {benchmarks[0].get('timestamp', 'N/A')}",
            f"**Setups compared**: {len(benchmarks)}",
            f"**Runs per setup**: min={min(all_runs)}, max={max(all_runs)}",
            f"**Syllabus file(s)**: {', '.join(all_syllabi) if all_syllabi else 'N/A'}",
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

        # Per-setup notes
        lines.extend(self._generate_setup_notes(benchmarks))
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
            "| Setup | Runs | Avg Time (s) | Quality (0-100) | Grades (F/G/A/U) | Judgment | RAG Triad (G/C/A) | Agent Calls | Status |",
            "|-------|------|--------------|------------------|------------------|----------|-------------------|-------------|---------|",
        ]

        for bench in sorted(benchmarks, key=lambda b: b["setup_metadata"]["setup_name"]):
            setup_name = bench["setup_metadata"]["setup_name"]
            avg = bench["average"]
            run_count = self._bench_num_runs(bench)

            # Timing
            avg_time = f"{avg['timing']['total_seconds']:.1f}"

            # Grades
            grades = self._avg_grades(bench)
            grades_str = (
                f"{grades['format']}/{grades['grounding']}/{grades['agenda']}/{grades['usability']}"
            )
            quality_score = f"{self._quality_score(bench):.1f}"

            # Judgment
            judgment = self._primary_judgment(bench)

            # RAG Triad
            rag = avg["rag_triad"]
            rag_str = f"{rag['groundedness']:.2f}/{rag['context_relevance']:.2f}/{rag['answer_relevance']:.2f}"

            # Agent calls
            agent_calls = int(avg["agent_calls"]["total"])

            # Status
            status = self._get_status(bench, benchmarks)

            lines.append(
                f"| {setup_name} | {run_count} | {avg_time} | {quality_score} | "
                f"{grades_str} | {judgment} | {rag_str} | {agent_calls} | {status} |"
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
            "| Setup | Runs | Grade Profile (F/G/A/U) | Quality (0-100) | Judgments (P/B/F) |",
            "|-------|------|-------------------------|------------------|-------------------|",
        ]

        for bench in sorted(benchmarks, key=lambda b: b["setup_metadata"]["setup_name"]):
            setup_name = bench["setup_metadata"]["setup_name"]
            run_count = self._bench_num_runs(bench)
            profile = self._grade_profile(bench)
            judgments = self._judgment_counts(bench)
            quality_score = self._quality_score(bench)

            profile_str = (
                f"{profile['format']}/{profile['grounding']}/"
                f"{profile['agenda']}/{profile['usability']}"
            )
            judgments_str = f"{judgments['PASS']}/{judgments['BORDERLINE']}/{judgments['FAIL']}"

            lines.append(
                f"| {setup_name} | {run_count} | {profile_str} | "
                f"{quality_score:.1f} | {judgments_str} |"
            )

        return lines

    def _generate_setup_notes(self, benchmarks: list[dict]) -> list[str]:
        """Generate short per-setup summaries, including failure hints."""
        lines = ["## Per-Setup Notes", ""]

        for bench in sorted(benchmarks, key=lambda b: b["setup_metadata"]["setup_name"]):
            setup_name = bench["setup_metadata"]["setup_name"]
            run_count = self._bench_num_runs(bench)
            judgment = self._primary_judgment(bench)
            quality_score = self._quality_score(bench)
            rag_avg = bench["average"]["rag_triad"]["average"]
            total_seconds = bench["average"]["timing"]["total_seconds"]
            notes = (
                f"{setup_name}: {judgment}, runs={run_count}, quality={quality_score:.1f}, "
                f"RAG={rag_avg:.3f}, avg_time={total_seconds:.1f}s."
            )

            fail_reason = self._failure_summary(bench)
            if fail_reason:
                notes += f" Why failed: {fail_reason}."

            lines.append(f"- {notes}")

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

        # Best quality (numeric score from multi-run average)
        best_quality = max(benchmarks, key=self._quality_score)
        lines.append(
            f"- **Best Quality**: {best_quality['setup_metadata']['setup_name']} "
            f"(Score: {self._quality_score(best_quality):.1f})"
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
        eligible = [bench for bench in benchmarks if self._primary_judgment(bench) == "PASS"]
        if not eligible:
            lines.append(
                "No PASS setup available for recommendation. Review Per-Setup Notes and rerun."
            )
            return lines

        # Find fastest
        fastest = min(eligible, key=lambda b: b["average"]["timing"]["total_seconds"])
        best_quality = max(eligible, key=self._quality_score)

        # Find best RAG
        best_rag = max(eligible, key=lambda b: b["average"]["rag_triad"]["average"])

        lines.append(
            f"1. **For speed-critical applications**: "
            f"Use **{fastest['setup_metadata']['setup_name']}** "
            f"({fastest['average']['timing']['total_seconds']:.1f}s average, PASS)"
        )

        lines.append(
            f"2. **For highest quality reports**: "
            f"Use **{best_quality['setup_metadata']['setup_name']}** "
            f"(Quality score: {self._quality_score(best_quality):.1f}, PASS)"
        )

        lines.append(
            f"3. **For best RAG performance**: "
            f"Use **{best_rag['setup_metadata']['setup_name']}** "
            f"(RAG Triad: {best_rag['average']['rag_triad']['average']:.3f}, PASS)"
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
        judgment = self._primary_judgment(bench)

        if judgment != "PASS":
            return "⚠️ Quality"
        elif avg_time > median_time * 1.3:
            return "⚠️ Slow"
        elif avg_time < median_time * 0.8:
            return "✅ Fast"
        else:
            return "✅"

    def _bench_num_runs(self, bench: dict) -> int:
        runs = bench.get("runs", [])
        return int(bench.get("num_runs", len(runs)))

    def _quality_score(self, bench: dict) -> float:
        avg_scores = bench.get("average", {}).get("scores", {})
        if "content_quality_100" in avg_scores:
            return float(avg_scores["content_quality_100"])

        runs = bench.get("runs", [])
        if not runs:
            return 0.0

        dimensions = ("format", "grounding", "agenda", "usability")
        values = []
        for run in runs:
            grades = run.get("quality_result", {}).get("grades", {})
            for dim in dimensions:
                values.append(GRADE_TO_SCORE.get(grades.get(dim, "E"), 30.0))
        return sum(values) / len(values) if values else 0.0

    def _judgment_counts(self, bench: dict) -> dict[str, int]:
        counter = Counter(
            run.get("quality_result", {}).get("judgment", "BORDERLINE")
            for run in bench.get("runs", [])
        )
        return {
            "PASS": counter.get("PASS", 0),
            "BORDERLINE": counter.get("BORDERLINE", 0),
            "FAIL": counter.get("FAIL", 0),
        }

    def _primary_judgment(self, bench: dict) -> str:
        counts = self._judgment_counts(bench)
        if counts["FAIL"] > 0:
            return "FAIL"
        if counts["PASS"] > 0:
            return "PASS"
        return "BORDERLINE"

    def _avg_grades(self, bench: dict) -> dict[str, str]:
        dimensions = ("format", "grounding", "agenda", "usability")
        runs = bench.get("runs", [])
        out: dict[str, str] = {}
        for dim in dimensions:
            numeric = []
            for run in runs:
                grade = run.get("quality_result", {}).get("grades", {}).get(dim, "E")
                numeric.append(GRADE_TO_SCORE.get(grade, 30.0))
            avg_score = sum(numeric) / len(numeric) if numeric else 30.0
            out[dim] = self._score_to_grade(avg_score)
        return out

    def _grade_profile(self, bench: dict) -> dict[str, str]:
        dimensions = ("format", "grounding", "agenda", "usability")
        runs = bench.get("runs", [])
        out: dict[str, str] = {}
        for dim in dimensions:
            values = [run.get("quality_result", {}).get("grades", {}).get(dim, "E") for run in runs]
            if not values:
                out[dim] = "E(0)"
                continue
            counter = Counter(values)
            top_grade, top_count = sorted(counter.items(), key=lambda item: (-item[1], item[0]))[0]
            out[dim] = f"{top_grade}({top_count}/{len(values)})"
        return out

    def _score_to_grade(self, score: float) -> str:
        for threshold, grade in SCORE_TO_GRADE:
            if score >= threshold:
                return grade
        return "E"

    def _failure_summary(self, bench: dict) -> str | None:
        if self._primary_judgment(bench) != "FAIL":
            return None

        missing_agenda = Counter()
        missing_raw_notes = Counter()
        off_topic = Counter()
        reasoning_fallback = ""

        for run in bench.get("runs", []):
            quality = run.get("quality_result", {})
            if quality.get("judgment") != "FAIL":
                continue
            for item in quality.get("missing_agenda_items", []):
                missing_agenda[item] += 1
            for item in quality.get("missing_raw_notes", []):
                missing_raw_notes[item] += 1
            for item in quality.get("off_topic_signals", []):
                off_topic[item] += 1
            if not reasoning_fallback and quality.get("reasoning"):
                reasoning_fallback = quality["reasoning"].split(".")[0].strip()

        details: list[str] = []
        if missing_agenda:
            details.append(f"missing agenda ({missing_agenda.most_common(1)[0][0]})")
        if missing_raw_notes:
            details.append(f"missing raw notes ({missing_raw_notes.most_common(1)[0][0]})")
        if off_topic:
            details.append(f"off-topic signals ({off_topic.most_common(1)[0][0]})")
        if details:
            return "; ".join(details[:2])
        if reasoning_fallback:
            return reasoning_fallback
        return "quality judge returned FAIL"


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
    print("\n" + "=" * 60)
    print(markdown)
    print("=" * 60)


if __name__ == "__main__":
    main()
