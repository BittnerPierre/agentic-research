"""Compare spike runs from their stats.json sidecars (issue #196).

Lightweight, format-agnostic: reads the benchmark stats written by
deep_manager._persist_benchmark_stats and prints a markdown comparison table.
No judge model, no trace parsing — just the objective metrics (speed,
efficiency, grounding proxy) so it runs anywhere, including the Mac.

    uv run spike-compare                       # scans benchmarks/runs
    uv run spike-compare benchmarks/runs/A benchmarks/runs/B
    uv run spike-compare --csv out.csv
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def _find_stats_files(paths: list[str]) -> list[Path]:
    targets = paths or ["benchmarks/runs"]
    files: list[Path] = []
    for raw in targets:
        p = Path(raw)
        if p.is_dir():
            files.extend(sorted(p.rglob("stats.json")))
        elif p.name == "stats.json" and p.is_file():
            files.append(p)
        elif p.is_file():  # a run directory passed as a file-ish path
            candidate = p / "stats.json"
            if candidate.is_file():
                files.append(candidate)
    return files


def _fmt(value, spec: str = "") -> str:
    if value is None:
        return "—"
    if spec:
        try:
            return format(value, spec)
        except (TypeError, ValueError):
            return str(value)
    return str(value)


# (header, extractor) — extractor pulls the cell value from a stats dict.
COLUMNS = [
    ("config", lambda s: s.get("config_name")),
    ("strategy", lambda s: s.get("writer_strategy")),
    ("writer_model", lambda s: (s.get("models") or {}).get("writer")),
    ("ok", lambda s: "✓" if s.get("success") else "✗"),
    ("total_s", lambda s: _fmt((s.get("timings") or {}).get("total"), ".1f")),
    ("writing_s", lambda s: _fmt((s.get("timings") or {}).get("writing"), ".1f")),
    (
        "write_tok/s",
        lambda s: _fmt((s.get("derived") or {}).get("writing_throughput_tok_s"), ".1f"),
    ),
    (
        "concurrency",
        lambda s: _fmt((s.get("writer_metrics") or {}).get("concurrency_ratio"), ".2f"),
    ),
    ("calls", lambda s: (s.get("agent_calls") or {}).get("total")),
    ("fails", lambda s: (s.get("agent_calls") or {}).get("failures")),
    ("n_src", lambda s: s.get("n_sources")),
    (
        "src_cov",
        lambda s: _fmt(
            ((s.get("writer_metrics") or {}).get("grounding") or {}).get("source_coverage"), ".0%"
        ),
    ),
]


def build_table(stats_list: list[dict]) -> str:
    """Render the comparison rows as a GitHub-flavored markdown table."""
    headers = [h for h, _ in COLUMNS]
    rows = [[_fmt(extract(s)) for _, extract in COLUMNS] for s in stats_list]
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    lines += ["| " + " | ".join(row) + " |" for row in rows]
    return "\n".join(lines)


def _to_csv(stats_list: list[dict]) -> str:
    headers = [h for h, _ in COLUMNS]
    out = [",".join(headers)]
    for s in stats_list:
        out.append(",".join(_fmt(extract(s)).replace(",", " ") for _, extract in COLUMNS))
    return "\n".join(out)


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare spike runs from stats.json sidecars")
    parser.add_argument(
        "paths",
        nargs="*",
        help="stats.json files or run directories (default: benchmarks/runs)",
    )
    parser.add_argument("--csv", help="also write a CSV to this path")
    args = parser.parse_args()

    files = _find_stats_files(args.paths)
    if not files:
        print("No stats.json found. Run agentic-research first (it writes benchmarks/runs/...).")
        return

    stats_list = [json.loads(f.read_text(encoding="utf-8")) for f in files]
    print(f"Comparing {len(stats_list)} run(s):\n")
    print(build_table(stats_list))

    if args.csv:
        Path(args.csv).write_text(_to_csv(stats_list), encoding="utf-8")
        print(f"\nCSV written to {args.csv}")


if __name__ == "__main__":
    main()
