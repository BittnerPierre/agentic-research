"""Grade spike runs for RAG groundedness against the retrieved corpus (issue #196).

The grounding reference is ``sources.json`` — what the search agents actually
retrieved — NOT the report itself. That is the whole point of moving aggregation
out of the writer: previously the eval read the writer's own RAW section, so an
empty/hallucinated RAW could fool it. Here groundedness is judged against the
concatenated retrieved sources.

Uses an OpenAI judge (neutral and constant across runs) so the comparison
between Mistral-Small-4 / MiniMax-M2.7 / Qwen3.6 stays fair.

    uv run spike-grade                              # grades benchmarks/runs
    uv run spike-grade benchmarks/runs/<run>
    uv run spike-grade --judge-model openai/gpt-4.1
"""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from .rag_triad_evaluator import evaluate_rag_triad


def find_run_dirs(paths: list[str]) -> list[Path]:
    """Run directories are those containing a stats.json."""
    targets = paths or ["benchmarks/runs"]
    dirs: list[Path] = []
    for raw in targets:
        p = Path(raw)
        if (p / "stats.json").is_file():
            dirs.append(p)
        elif p.is_dir():
            dirs.extend(sorted(d.parent for d in p.rglob("stats.json")))
    # de-dup while keeping order
    seen: dict[Path, None] = {}
    for d in dirs:
        seen.setdefault(d, None)
    return list(seen)


def corpus_from_sources(sources: list[dict]) -> str:
    """Rebuild the labelled [S#] corpus from a sources.json payload."""
    blocks = [
        f"### [{s.get('source_id')}] {s.get('topic')}\n"
        f"(source: {s.get('file_name')})\n\n{s.get('content', '')}"
        for s in sources
    ]
    return "\n\n".join(blocks)


def _locate_report(stats: dict, output_dir: str) -> Path | None:
    name = stats.get("report_file")
    if not name:
        return None
    candidate = Path(output_dir) / name
    return candidate if candidate.is_file() else None


async def grade_run(run_dir: Path, judge_model: str, output_dir: str) -> dict | None:
    """Grade one run; write grounding.json into its directory. Returns the scores."""
    stats = json.loads((run_dir / "stats.json").read_text(encoding="utf-8"))
    sources_path = run_dir / "sources.json"
    if not sources_path.is_file():
        print(f"  skip {run_dir.name}: no sources.json")
        return None
    sources = json.loads(sources_path.read_text(encoding="utf-8"))

    report_path = _locate_report(stats, output_dir)
    if report_path is None:
        print(
            f"  skip {run_dir.name}: report '{stats.get('report_file')}' not found in {output_dir}"
        )
        return None

    corpus = corpus_from_sources(sources)
    triad = await evaluate_rag_triad(
        report_path.read_text(encoding="utf-8"),
        corpus,
        stats.get("query", ""),
        judge_model=judge_model,
    )
    data = triad.model_dump() if hasattr(triad, "model_dump") else dict(triad)
    data["judge_model"] = judge_model
    (run_dir / "grounding.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return data


async def _amain(args: argparse.Namespace) -> None:
    run_dirs = find_run_dirs(args.paths)
    if not run_dirs:
        print("No run directories with stats.json found.")
        return

    print(f"Grading {len(run_dirs)} run(s) with judge={args.judge_model}\n")
    for run_dir in run_dirs:
        data = await grade_run(run_dir, args.judge_model, args.output_dir)
        if data is None:
            continue
        print(
            f"  {run_dir.name}: grounded={data['groundedness']:.2f} "
            f"context={data['context_relevance']:.2f} answer={data['answer_relevance']:.2f} "
            f"avg={data['average']:.2f}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Grade spike runs for RAG groundedness")
    parser.add_argument(
        "paths", nargs="*", help="run dirs or a parent dir (default: benchmarks/runs)"
    )
    parser.add_argument(
        "--judge-model", default="openai/gpt-4.1-mini", help="OpenAI judge model id"
    )
    parser.add_argument("--output-dir", default="output", help="where report .md files live")
    asyncio.run(_amain(parser.parse_args()))


if __name__ == "__main__":
    main()
