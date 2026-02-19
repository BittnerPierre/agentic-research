"""
Benchmark Comparator - Compare and visualize benchmark results

Aggregates results from multiple setup benchmarks and generates
comparison tables in Markdown format.
"""

import argparse
import json
from collections import Counter
from pathlib import Path
from statistics import mean, pstdev

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
        failures = [bench for bench in benchmarks if bench.get("status") == "FAILED"]
        successes = [bench for bench in benchmarks if bench.get("status") != "FAILED"]

        if not successes:
            return self._generate_failure_only_report(failures)

        all_runs = [self._bench_num_runs(bench) for bench in successes]
        all_syllabi = sorted(
            {
                bench.get("syllabus_file", "N/A")
                for bench in successes
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
        lines.extend(self._generate_summary_table(successes))
        lines.append("")

        # Legend
        lines.extend(self._generate_legend())
        lines.append("")

        # Detailed Timing Table
        lines.extend(self._generate_timing_table(successes))
        lines.append("")

        # Token usage table
        lines.extend(self._generate_usage_table(successes))
        lines.append("")

        # RAG Triad Table
        lines.extend(self._generate_rag_triad_table(successes))
        lines.append("")

        # Quality Grades Table
        lines.extend(self._generate_quality_table(successes))
        lines.append("")

        # Stability metrics
        lines.extend(self._generate_stability_table(successes))
        lines.append("")

        # Detailed per-run diagnostics
        lines.extend(self._generate_run_details_table(successes))
        lines.append("")

        # Warmup + steady-state details (if configured)
        lines.extend(self._generate_warmup_table(successes))
        if lines[-1] != "":
            lines.append("")

        # Failures summary
        lines.extend(self._generate_failures_table(failures))
        if lines[-1] != "":
            lines.append("")

        # Per-setup notes
        lines.extend(self._generate_setup_notes(successes))
        lines.append("")

        # Podium
        lines.extend(self._generate_podium(successes))
        lines.append("")

        # Best Performers
        lines.extend(self._generate_best_performers(successes))
        lines.append("")

        # Recommendations
        lines.extend(self._generate_recommendations(successes))

        return "\n".join(lines)

    def _generate_failure_only_report(self, failures: list[dict]) -> str:
        lines = [
            "# Benchmark Comparison Report",
            "",
            "**Status**: No successful benchmark results found.",
            "",
        ]
        lines.extend(self._generate_failures_table(failures))
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

            # Verdict
            judgment = self._verdict(bench)

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

    def _generate_legend(self) -> list[str]:
        return [
            "## Legend",
            "",
            "- `F/G/A/U` = `Format / Grounding / Agenda / Usability`.",
            "- `A+` = grade stable across all runs, `A` = mostly stable, `A-` = unstable.",
            "- `P/B/F` = `PASS / BORDERLINE / FAIL` counts across runs.",
            "- `Quality (0-100)` is the averaged content-quality score across runs.",
            "- Token usage fields are averaged across runs when available; `N/A` indicates missing usage.",
            "- Aggregation rule: mean for `<5` runs; trimmed mean (drop min/max) for `>=5` runs.",
            "- If warmup reporting is enabled, averages exclude run 1.",
            "- If drop-worst-run is enabled, averages exclude the slowest run by total time.",
            "- `Judgment` is an aggregated verdict: `EXCELLENT`, `STRONG`, `PASS`, `ACCEPTABLE`, `FAIL`.",
            "- `ACCEPTABLE` means usable but with notable weaknesses in at least one run.",
        ]

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

    def _generate_usage_table(self, benchmarks: list[dict]) -> list[str]:
        """Generate token usage table."""
        lines = [
            "## Token Usage",
            "",
            "| Setup | Input Tokens | Output Tokens | Total Tokens | Cached Tokens | Reasoning Tokens |",
            "|-------|--------------|---------------|--------------|---------------|------------------|",
        ]

        for bench in sorted(benchmarks, key=lambda b: b["setup_metadata"]["setup_name"]):
            setup_name = bench["setup_metadata"]["setup_name"]
            input_tokens = self._format_usage_metric(bench, "input_tokens")
            output_tokens = self._format_usage_metric(bench, "output_tokens")
            total_tokens = self._format_usage_metric(bench, "total_tokens")
            cached_tokens = self._format_usage_metric(bench, "cached_tokens")
            reasoning_tokens = self._format_usage_metric(bench, "reasoning_tokens")

            lines.append(
                f"| {setup_name} | {input_tokens} | {output_tokens} | {total_tokens} | "
                f"{cached_tokens} | {reasoning_tokens} |"
            )

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
            "| Setup | Runs | Avg Grades (F/G/A/U) | Quality (0-100) | Quality Std | Judgments (P/B/F) | Verdict |",
            "|-------|------|----------------------|------------------|-------------|-------------------|---------|",
        ]

        for bench in sorted(benchmarks, key=lambda b: b["setup_metadata"]["setup_name"]):
            setup_name = bench["setup_metadata"]["setup_name"]
            run_count = self._bench_num_runs(bench)
            profile = self._avg_grades(bench)
            judgments = self._judgment_counts(bench)
            quality_score = self._quality_score(bench)
            quality_std = self._quality_std(bench)

            profile_str = (
                f"{profile['format']}/{profile['grounding']}/"
                f"{profile['agenda']}/{profile['usability']}"
            )
            judgments_str = f"{judgments['PASS']}/{judgments['BORDERLINE']}/{judgments['FAIL']}"

            lines.append(
                f"| {setup_name} | {run_count} | {profile_str} | "
                f"{quality_score:.1f} | {quality_std:.1f} | {judgments_str} | {self._verdict(bench)} |"
            )

        return lines

    def _generate_stability_table(self, benchmarks: list[dict]) -> list[str]:
        lines = [
            "## Stability Metrics",
            "",
            "| Setup | Time Std (s) | Quality Std | RAG Std | Aggregation |",
            "|-------|--------------|-------------|---------|-------------|",
        ]
        for bench in sorted(benchmarks, key=lambda b: b["setup_metadata"]["setup_name"]):
            setup_name = bench["setup_metadata"]["setup_name"]
            lines.append(
                f"| {setup_name} | {self._time_std(bench):.1f} | {self._quality_std(bench):.1f} | "
                f"{self._rag_std(bench):.3f} | {self._aggregation_label(bench)} |"
            )
        return lines

    def _generate_run_details_table(self, benchmarks: list[dict]) -> list[str]:
        lines = [
            "## Run Details",
            "",
            "| Setup | Run | Time (s) | Quality | Judgment | Grades (F/G/A/U) | RAG Avg |",
            "|-------|-----|----------|---------|----------|------------------|---------|",
        ]
        for bench in sorted(benchmarks, key=lambda b: b["setup_metadata"]["setup_name"]):
            setup_name = bench["setup_metadata"]["setup_name"]
            for idx, run in enumerate(bench.get("runs", []), start=1):
                timing = float(run.get("timing", {}).get("total_seconds", 0.0))
                quality = self._run_quality_score(run)
                judgment = run.get("quality_result", {}).get("judgment", "BORDERLINE")
                grades = run.get("quality_result", {}).get("grades", {})
                grades_str = (
                    f"{grades.get('format', 'E')}/{grades.get('grounding', 'E')}/"
                    f"{grades.get('agenda', 'E')}/{grades.get('usability', 'E')}"
                )
                rag_avg = float(run.get("rag_triad", {}).get("average", 0.0))
                lines.append(
                    f"| {setup_name} | {idx} | {timing:.1f} | {quality:.1f} | "
                    f"{judgment} | {grades_str} | {rag_avg:.3f} |"
                )
        return lines

    def _generate_failures_table(self, failures: list[dict]) -> list[str]:
        if not failures:
            return []
        lines = [
            "## Failures",
            "",
            "| Setup | Error | Log File |",
            "|-------|-------|----------|",
        ]
        for bench in sorted(failures, key=lambda b: b["setup_metadata"]["setup_name"]):
            setup_name = bench["setup_metadata"]["setup_name"]
            error = str(bench.get("error_message") or "Unknown failure")
            log_file = str(bench.get("log_file") or "N/A")
            lines.append(f"| {setup_name} | {error} | {log_file} |")
        return lines

    def _generate_warmup_table(self, benchmarks: list[dict]) -> list[str]:
        eligible = [
            bench
            for bench in benchmarks
            if bench.get("report_warmup") or bench.get("drop_worst_run")
        ]
        if not eligible:
            return []

        lines = [
            "## Warmup / Steady-State",
            "",
            "| Setup | Warmup Run | Warmup Time (s) | Warmup Quality | Avg Runs | Avg Time (s) | Avg Quality | Dropped Run |",
            "|-------|------------|-----------------|----------------|----------|--------------|-------------|-------------|",
        ]

        for bench in sorted(eligible, key=lambda b: b["setup_metadata"]["setup_name"]):
            setup_name = bench["setup_metadata"]["setup_name"]
            warmup_idx = bench.get("warmup_run_index")
            warmup_run = None
            if warmup_idx is not None and warmup_idx < len(bench.get("runs", [])):
                warmup_run = bench["runs"][warmup_idx]

            warmup_label = str(warmup_idx + 1) if warmup_idx is not None else "N/A"
            warmup_time = (
                f"{float(warmup_run.get('timing', {}).get('total_seconds', 0.0)):.1f}"
                if warmup_run
                else "N/A"
            )
            warmup_quality = f"{self._run_quality_score(warmup_run):.1f}" if warmup_run else "N/A"

            avg_indices = bench.get("average_run_indices", [])
            avg_runs = ", ".join(str(i + 1) for i in avg_indices) if avg_indices else "N/A"
            avg_time = f"{bench['average']['timing']['total_seconds']:.1f}"
            avg_quality = f"{self._quality_score(bench):.1f}"

            dropped_idx = bench.get("dropped_run_index")
            dropped_label = str(dropped_idx + 1) if dropped_idx is not None else "N/A"

            lines.append(
                f"| {setup_name} | {warmup_label} | {warmup_time} | {warmup_quality} | "
                f"{avg_runs} | {avg_time} | {avg_quality} | {dropped_label} |"
            )

        return lines

    def _generate_setup_notes(self, benchmarks: list[dict]) -> list[str]:
        """Generate short per-setup summaries, including failure hints."""
        lines = ["## Per-Setup Notes", ""]

        for bench in sorted(benchmarks, key=lambda b: b["setup_metadata"]["setup_name"]):
            setup_name = bench["setup_metadata"]["setup_name"]
            run_count = self._bench_num_runs(bench)
            judgment = self._verdict(bench)
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

    def _generate_podium(self, benchmarks: list[dict]) -> list[str]:
        lines = ["## Podium (Top 3)", ""]
        eligible = [b for b in benchmarks if self._is_recommendable(b)]
        ranked = sorted(
            eligible,
            key=lambda b: (
                self._overall_score(b),
                self._quality_score(b),
                b["average"]["rag_triad"]["average"],
            ),
            reverse=True,
        )[:3]

        if not ranked:
            lines.append("- No recommendable setup available (all setups are FAIL).")
            return lines

        for idx, bench in enumerate(ranked, start=1):
            setup = bench["setup_metadata"]["setup_name"]
            lines.append(
                f"{idx}. {setup} - overall={self._overall_score(bench):.1f}, "
                f"quality={self._quality_score(bench):.1f}, "
                f"RAG={bench['average']['rag_triad']['average']:.3f}, "
                f"time={bench['average']['timing']['total_seconds']:.1f}s, "
                f"verdict={self._verdict(bench)}"
            )

        return lines

    def _generate_best_performers(self, benchmarks: list[dict]) -> list[str]:
        """Identify and list best performers by category."""
        lines = ["## Best Performers", ""]
        eligible = [b for b in benchmarks if self._is_recommendable(b)]
        candidate_pool = eligible if eligible else benchmarks

        # Fastest
        fastest = min(candidate_pool, key=lambda b: b["average"]["timing"]["total_seconds"])
        lines.append(
            f"- **Fastest**: {fastest['setup_metadata']['setup_name']} "
            f"({fastest['average']['timing']['total_seconds']:.1f}s)"
        )

        # Best RAG Triad
        best_rag = max(candidate_pool, key=lambda b: b["average"]["rag_triad"]["average"])
        lines.append(
            f"- **Best RAG Triad**: {best_rag['setup_metadata']['setup_name']} "
            f"(avg: {best_rag['average']['rag_triad']['average']:.3f})"
        )

        # Best quality (numeric score from multi-run average)
        best_quality = max(candidate_pool, key=self._quality_score)
        lines.append(
            f"- **Best Quality**: {best_quality['setup_metadata']['setup_name']} "
            f"(Score: {self._quality_score(best_quality):.1f})"
        )

        # Most efficient (fewest calls)
        most_efficient = min(candidate_pool, key=lambda b: b["average"]["agent_calls"]["total"])
        lines.append(
            f"- **Most Efficient**: {most_efficient['setup_metadata']['setup_name']} "
            f"({int(most_efficient['average']['agent_calls']['total'])} agent calls)"
        )

        return lines

    def _generate_recommendations(self, benchmarks: list[dict]) -> list[str]:
        """Generate recommendations based on results."""
        lines = ["## Recommendations", ""]
        eligible = [bench for bench in benchmarks if self._is_recommendable(bench)]
        if not eligible:
            lines.append("No recommendable setup available. Review Per-Setup Notes and rerun.")
            return lines

        # Find fastest
        fastest = min(eligible, key=lambda b: b["average"]["timing"]["total_seconds"])
        best_quality = max(eligible, key=self._quality_score)

        # Find best RAG
        best_rag = max(eligible, key=lambda b: b["average"]["rag_triad"]["average"])

        lines.append(
            f"1. **For speed-critical applications**: "
            f"Use **{fastest['setup_metadata']['setup_name']}** "
            f"({fastest['average']['timing']['total_seconds']:.1f}s average, {self._verdict(fastest)})"
        )

        lines.append(
            f"2. **For highest quality reports**: "
            f"Use **{best_quality['setup_metadata']['setup_name']}** "
            f"(Quality score: {self._quality_score(best_quality):.1f}, {self._verdict(best_quality)})"
        )

        lines.append(
            f"3. **For best RAG performance**: "
            f"Use **{best_rag['setup_metadata']['setup_name']}** "
            f"(RAG Triad: {best_rag['average']['rag_triad']['average']:.3f}, {self._verdict(best_rag)})"
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
        judgment = self._verdict(bench)

        if judgment in {"FAIL"}:
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
        values = [self._run_quality_score(run) for run in bench.get("runs", [])]
        if values:
            return self._aggregate_values(values)
        avg_scores = bench.get("average", {}).get("scores", {})
        return float(avg_scores.get("content_quality_100", 0.0))

    def _quality_std(self, bench: dict) -> float:
        values = [self._run_quality_score(run) for run in bench.get("runs", [])]
        return self._std_values(values)

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

    def _verdict(self, bench: dict) -> str:
        counts = self._judgment_counts(bench)
        runs = max(self._bench_num_runs(bench), 1)
        fail_ratio = counts["FAIL"] / runs
        quality = self._quality_score(bench)

        if fail_ratio >= 0.5 or quality < 65.0:
            return "FAIL"
        if counts["FAIL"] > 0:
            return "ACCEPTABLE"
        if quality >= 95.0 and counts["PASS"] == runs:
            return "EXCELLENT"
        if quality >= 85.0:
            return "STRONG"
        return "PASS"

    def _is_recommendable(self, bench: dict) -> bool:
        return self._verdict(bench) != "FAIL"

    def _overall_score(self, bench: dict) -> float:
        values = [
            float(run.get("scores", {}).get("overall_100"))
            for run in bench.get("runs", [])
            if run.get("scores", {}).get("overall_100") is not None
        ]
        if values:
            return self._aggregate_values(values)
        avg_scores = bench.get("average", {}).get("scores", {})
        if "overall_100" in avg_scores:
            return float(avg_scores["overall_100"])
        # Fallback for older artifacts missing normalized scores.
        rag = float(bench.get("average", {}).get("rag_triad", {}).get("average", 0.0)) * 100.0
        quality = self._quality_score(bench)
        return round((0.7 * quality) + (0.3 * rag), 2)

    def _avg_grades(self, bench: dict) -> dict[str, str]:
        dimensions = ("format", "grounding", "agenda", "usability")
        runs = bench.get("runs", [])
        out: dict[str, str] = {}
        for dim in dimensions:
            numeric = [self._run_dimension_score(run, dim) for run in runs]
            avg_score = self._aggregate_values(numeric) if numeric else 30.0
            base_grade = self._score_to_grade(avg_score)
            out[dim] = self._grade_with_stability(base_grade, runs, dim)
        return out

    def _score_to_grade(self, score: float) -> str:
        for threshold, grade in SCORE_TO_GRADE:
            if score >= threshold:
                return grade
        return "E"

    def _grade_with_stability(self, base_grade: str, runs: list[dict], dim: str) -> str:
        run_count = len(runs)
        if run_count <= 1:
            return base_grade
        same_as_base = 0
        for run in runs:
            run_grade = run.get("quality_result", {}).get("grades", {}).get(dim, "E")
            if run_grade == base_grade:
                same_as_base += 1
        ratio = same_as_base / run_count
        if ratio == 1.0:
            return f"{base_grade}+"
        if ratio >= (2 / 3):
            return base_grade
        return f"{base_grade}-"

    def _run_dimension_score(self, run: dict, dim: str) -> float:
        grade = run.get("quality_result", {}).get("grades", {}).get(dim, "E")
        return GRADE_TO_SCORE.get(grade, 30.0)

    def _run_quality_score(self, run: dict) -> float:
        score = run.get("scores", {}).get("content_quality_100")
        if score is not None:
            return float(score)
        grades = run.get("quality_result", {}).get("grades", {})
        return (
            GRADE_TO_SCORE.get(grades.get("grounding", "E"), 30.0) * 0.40
            + GRADE_TO_SCORE.get(grades.get("agenda", "E"), 30.0) * 0.25
            + GRADE_TO_SCORE.get(grades.get("format", "E"), 30.0) * 0.20
            + GRADE_TO_SCORE.get(grades.get("usability", "E"), 30.0) * 0.15
        )

    def _aggregate_values(self, values: list[float]) -> float:
        if not values:
            return 0.0
        if len(values) >= 5:
            sorted_vals = sorted(values)
            trimmed = sorted_vals[1:-1]
            return float(mean(trimmed)) if trimmed else float(mean(sorted_vals))
        return float(mean(values))

    def _std_values(self, values: list[float]) -> float:
        if len(values) <= 1:
            return 0.0
        return float(pstdev(values))

    def _aggregation_label(self, bench: dict) -> str:
        return "trimmed mean (drop min/max)" if self._bench_num_runs(bench) >= 5 else "mean"

    def _time_std(self, bench: dict) -> float:
        values = [
            float(run.get("timing", {}).get("total_seconds", 0.0))
            for run in bench.get("runs", [])
            if run.get("timing", {}).get("total_seconds") is not None
        ]
        return self._std_values(values)

    def _rag_std(self, bench: dict) -> float:
        values = [
            float(run.get("rag_triad", {}).get("average", 0.0))
            for run in bench.get("runs", [])
            if run.get("rag_triad", {}).get("average") is not None
        ]
        return self._std_values(values)

    def _failure_summary(self, bench: dict) -> str | None:
        if self._verdict(bench) != "FAIL":
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

    def _usage_values(self, bench: dict, key: str) -> list[float]:
        values: list[float] = []
        for run in bench.get("runs", []):
            usage = run.get("usage") or {}
            value = usage.get(key)
            if value is None:
                continue
            values.append(float(value))
        return values

    def _format_usage_metric(self, bench: dict, key: str) -> str:
        values = self._usage_values(bench, key)
        if not values:
            avg_usage = bench.get("average", {}).get("usage", {})
            avg_value = avg_usage.get(key)
            if avg_value is None:
                return "N/A"
            try:
                return f"{float(avg_value):.1f}"
            except (TypeError, ValueError):
                return "N/A"
        return f"{self._aggregate_values(values):.1f}"


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
