"""Grade spike runs for report quality (issue #196), all against the retrieved corpus.

The grounding/quality reference is ``sources.json`` — what the search agents
actually retrieved — NOT the report itself. That is the whole point of moving
aggregation out of the writer: the classic benchmark judged grounding on the
writer's own RAW section, so a report that ignored the references could still win
(this happened — Qwen ranked #1 without reading the sources). Here every judge
sees the retrieved sources as the source of truth.

Three judged axes, written to grade.json per run:
- RAG triad (groundedness / context relevance / answer relevance)
- report quality (LLM grades: grounding / agenda / format / usability)
- spec / syllabus compliance

Scoring philosophy (deliberately different from the classic benchmark, which we
do NOT touch):
- **Quality dominates**; speed/efficiency/tokens stay separate objective axes in
  spike-compare and are NOT folded into this score.
- **Grounding is a gate**: an ungrounded report cannot rank high, regardless of
  how polished it reads — fixing the false positive above.

Uses an OpenAI judge (neutral, constant across runs) for fairness between models.
The judge must be STRONG: gpt-4.1-mini rationalizes fabricated statistics as supported
(it scored a report full of invented figures 0.95 where gpt-4.1 caught them at 0.40), so
the default judge is gpt-4.1. Grounding is checked claim-by-claim against the sources.

    uv run spike-grade                              # grades benchmarks/runs
    uv run spike-grade benchmarks/runs/<run>
    uv run spike-grade --judge-model openai/gpt-4.1
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path

from agents import Agent, Runner
from src.agents.schemas import SourceDocument
from src.report_writer.aggregate import render_corpus

from .rag_triad_evaluator import evaluate_rag_triad
from .schemas import EvaluationResult
from .scoring import quality_score_100
from .spec_compliance_evaluator import evaluate_spec_compliance


def _load_dotenv() -> None:
    """Load .env so the OpenAI judge finds OPENAI_API_KEY.

    The main app loads it via src.config, but this CLI entry point runs
    standalone (uv run spike-grade) and never imports that module.
    """
    try:
        from dotenv import find_dotenv, load_dotenv
    except ImportError:  # python-dotenv absent: rely on the ambient env
        return
    dotenv_path = find_dotenv(usecwd=True)
    load_dotenv(dotenv_path, override=False)
    if os.getenv("OPENAI_API_KEY") == "":
        load_dotenv(dotenv_path, override=True)


# Quality composite weights (quality-first; NO speed term on purpose).
W_QUALITY, W_RAG, W_SPEC = 0.40, 0.35, 0.25

SPIKE_QUALITY_PROMPT = """You are an evaluation judge for a research report produced by an
agentic RAG workflow. You receive the RETRIEVED SOURCES (the only knowledge the report was
allowed to use), the QUERY, and the REPORT.

Grade each axis A-E (A best):
- grounding: verify the report's claims CLAIM BY CLAIM against the RETRIEVED SOURCES. Be strict on
  SPECIFIC claims (numbers, percentages, monetary amounts, dates, benchmark figures, named
  studies/tools): the same fact must actually appear in the sources. A bracket citation like [S3]
  is NOT proof — check the source truly contains the claim. Any fabricated specific (a plausible
  but invented statistic/table/study dressed with a citation) is a hallucination and must drop this
  grade to D or E, regardless of how polished the prose is.
- agenda: does the report cover the aspects the QUERY asks for (completeness, no gaps)?
- format: well-structured markdown — clear sections, a sources/references section, inline
  citations where appropriate.
- usability: readable, coherent, non-redundant, genuinely useful to a reader.

Also set: judgment (PASS / FAIL / BORDERLINE); reasoning (4-6 sentences). Use missing_raw_notes
for claims that are unsupported by the retrieved sources, missing_agenda_items for query aspects
left uncovered, and off_topic_signals for any reliance on external knowledge or off-topic drift.

Return the structured result.
"""


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
    seen: dict[Path, None] = {}
    for d in dirs:
        seen.setdefault(d, None)
    return list(seen)


def corpus_from_sources(sources: list[dict]) -> str:
    """Rebuild the labelled [S#] corpus from a sources.json payload.

    Reuses the writer-side render_corpus so the judge sees byte-for-byte the same
    corpus the chapter writers saw — no drift if that format is ever tweaked.
    """
    docs = [SourceDocument(**s) for s in sources]
    return render_corpus(docs)


def _locate_report(stats: dict, output_dir: str) -> Path | None:
    name = stats.get("report_file")
    if not name:
        return None
    # Prefer the output dir the run actually used (recorded in stats), so a run
    # made with a custom --output-dir stays gradable; fall back to the CLI value.
    for base in (stats.get("output_dir"), output_dir):
        if not base:
            continue
        candidate = Path(base) / name
        if candidate.is_file():
            return candidate
    return None


async def evaluate_quality(
    report_markdown: str, corpus: str, query: str, judge_model: str
) -> EvaluationResult:
    """LLM quality grades (format/grounding/agenda/usability) against the retrieved corpus."""
    judge = Agent(
        name="spike_quality_judge",
        instructions=SPIKE_QUALITY_PROMPT,
        model=judge_model,
        output_type=EvaluationResult,
    )
    input_text = f"===RETRIEVED SOURCES===\n{corpus}\n\n===QUERY===\n{query}\n\n===REPORT===\n{report_markdown}\n"
    result = await Runner.run(judge, input_text)
    return result.final_output_as(EvaluationResult)


def spike_overall(
    quality_100: float, rag_average: float, spec_100: float, groundedness: float
) -> float:
    """Quality-first composite with a grounding gate (no speed term)."""
    rag_100 = max(0.0, min(100.0, rag_average * 100.0))
    overall = W_QUALITY * quality_100 + W_RAG * rag_100 + W_SPEC * spec_100
    # An ungrounded report cannot rank high, however polished it reads.
    if groundedness < 0.4:
        overall = min(overall, 50.0)
    elif groundedness < 0.6:
        overall = min(overall, 70.0)
    return round(overall, 2)


async def grade_run(run_dir: Path, judge_model: str, output_dir: str) -> dict | None:
    """Grade one run on quality/grounding/spec; write grade.json. Returns the scores."""
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
    query = stats.get("query", "")
    report_md = report_path.read_text(encoding="utf-8")

    # All judges see the retrieved corpus as the source of truth; run them concurrently.
    triad, quality, spec = await asyncio.gather(
        evaluate_rag_triad(report_md, corpus, query, judge_model=judge_model),
        evaluate_quality(report_md, corpus, query, judge_model),
        evaluate_spec_compliance(report_md, query, corpus, judge_model=judge_model),
    )

    triad_d = triad.model_dump() if hasattr(triad, "model_dump") else dict(triad)
    quality_100 = quality_score_100(quality)
    spec_d = spec.model_dump() if hasattr(spec, "model_dump") else dict(spec)
    overall = spike_overall(
        quality_100, triad_d["average"], spec_d["score_100"], triad_d["groundedness"]
    )

    grade = {
        "judge_model": judge_model,
        "rag_triad": triad_d,
        "quality": {
            "grades": quality.grades.model_dump(),
            "quality_100": quality_100,
            "judgment": quality.judgment,
            "reasoning": quality.reasoning,
        },
        "spec": {
            "score_100": spec_d.get("score_100"),
            "violations": spec_d.get("violations", []),
            "unauthorized_sources": spec_d.get("unauthorized_sources", []),
        },
        "overall_quality_100": overall,
    }
    (run_dir / "grade.json").write_text(
        json.dumps(grade, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return grade


async def _amain(args: argparse.Namespace) -> None:
    run_dirs = find_run_dirs(args.paths)
    if not run_dirs:
        print("No run directories with stats.json found.")
        return

    print(f"Grading {len(run_dirs)} run(s) with judge={args.judge_model}\n")
    for run_dir in run_dirs:
        grade = await grade_run(run_dir, args.judge_model, args.output_dir)
        if grade is None:
            continue
        rag = grade["rag_triad"]
        print(
            f"  {run_dir.name}: grounded={rag['groundedness']:.2f} "
            f"quality={grade['quality']['quality_100']:.0f} "
            f"spec={grade['spec']['score_100']:.0f} "
            f"overall={grade['overall_quality_100']:.0f}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Grade spike runs for report quality/grounding/spec"
    )
    parser.add_argument(
        "paths", nargs="*", help="run dirs or a parent dir (default: benchmarks/runs)"
    )
    parser.add_argument(
        # gpt-4.1-mini is too credulous for claim-by-claim grounding: it rationalizes
        # fabricated statistics as "found or implied" (verified — it scored a report full
        # of invented figures 0.95, while gpt-4.1 caught them and scored 0.40). Default to
        # the stronger judge; grading a handful of runs is cheap enough.
        "--judge-model",
        default="openai/gpt-4.1",
        help="OpenAI judge model id (strong model recommended for reliable grounding)",
    )
    parser.add_argument("--output-dir", default="output", help="where report .md files live")
    _load_dotenv()
    asyncio.run(_amain(parser.parse_args()))


if __name__ == "__main__":
    main()
